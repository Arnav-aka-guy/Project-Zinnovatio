"""Who is told what, when. Called from `log_event`, inside the same transaction.

Every important change in Vaari already writes an event_log row (a slot
planned, a request that will miss, a job started or done, a flagged job, a
machine taken off, an account locked). This module turns those events into
queued notifications, so a message exists if and only if the change is
committed (an outbox). Delivery happens later in `dispatch.py`.

Pure bookkeeping: no network here, and nothing in this module may stop the
action that caused it (`log_event` catches every error).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app import clock
from app.config import settings
from app.models import Farmer, Machine, Notification, Plot, Request, ServiceRecord, Slot, UserAccount
from app.notify import messages as M

STAFF_CHANNELS = ("inapp", "webpush")


def _key_exists(session: Session, key: str) -> bool:
    for obj in session.new:
        if isinstance(obj, Notification) and obj.dedupe_key == key:
            return True
    with session.no_autoflush:
        return session.query(Notification.id).filter_by(dedupe_key=key).first() is not None


def queue(session: Session, *, key: str, **fields) -> Notification | None:
    """Add one notification unless the same one exists (by dedupe key)."""
    if _key_exists(session, key):
        return None
    now = clock.now_utc()
    channel = fields["channel"]
    n = Notification(
        dedupe_key=key,
        status="delivered" if channel == "inapp" else "queued",
        sent_at=now if channel == "inapp" else None,
        next_attempt_at=None if channel == "inapp" else now,
        attempts=0,
        created_at=now,
        urgency=fields.pop("urgency", "normal"),
        lang=fields.pop("lang", "en"),
        **fields,
    )
    session.add(n)
    if channel != "inapp":
        session.info["vaari_notify_pending"] = True  # wakes the sender right after commit
    return n


# ── Audiences ────────────────────────────────────────────────────────────
def queue_farmer(session: Session, kind: str, req: Request, *, slot: Slot | None = None, extra_key: str = "") -> None:
    if settings.notify_mode == "off":
        return
    farmer = session.get(Farmer, req.farmer_id)
    if farmer is None or not farmer.consent_service:
        return
    plot = session.get(Plot, req.plot_id)
    machine = session.get(Machine, slot.machine_id) if slot else None
    record = None
    if kind == "job_done" and slot is not None:
        with session.no_autoflush:
            record = session.query(ServiceRecord).filter_by(slot_id=slot.id).first()
    lang = "pa" if (farmer.language or "pa") == "pa" else "en"
    ctx = M.farmer_context(
        plot=plot, req=req, slot=slot, machine=machine, record_token=record.token if record else None
    )
    body = M.farmer_text(kind, lang, ctx)
    channel = settings.farmer_channels[0]
    ref = f"slot:{slot.id}" if slot else f"request:{req.id}"
    queue(
        session,
        key=f"farmer:{kind}:{ref}{extra_key}:{channel}",
        kind=kind,
        audience="farmer",
        channel=channel,
        farmer_id=farmer.id,
        request_id=req.id,
        slot_id=slot.id if slot else None,
        machine_id=slot.machine_id if slot else None,
        lang=lang,
        body=body,
        urgency="high" if kind in ("slot_scheduled", "slot_changed", "job_started") else "normal",
    )


def queue_staff(
    session: Session,
    kind: str,
    audience: str,
    key: str,
    *,
    url: str,
    urgency: str = "normal",
    request_id: int | None = None,
    slot_id: int | None = None,
    machine_id: int | None = None,
    **v,
) -> None:
    title, body = M.staff_alert(kind, request_id=request_id, **v)
    for channel in STAFF_CHANNELS:
        queue(
            session,
            key=f"{audience}:{kind}:{key}:{channel}",
            kind=kind,
            audience=audience,
            channel=channel,
            title=title,
            body=body,
            url=url,
            urgency=urgency,
            request_id=request_id,
            slot_id=slot_id,
            machine_id=machine_id,
        )


def queue_driver(session: Session, kind: str, machine: Machine, key: str, **v) -> None:
    title, body = M.driver_alert(kind, **v)
    queue(
        session,
        key=f"driver:{kind}:{key}",
        kind=kind,
        audience="driver",
        channel="webpush",
        machine_id=machine.id,
        title=title,
        body=body,
        url=f"/driver/{machine.link_token}",
        urgency="high" if kind != "driver_day_plan" else "normal",
    )


def _soon(d: date) -> bool:
    """Today or tomorrow: worth telling the driver right away."""
    today = clock.today()
    return today <= d <= today + timedelta(days=1)


def _request_bits(session: Session, req: Request) -> dict:
    plot = session.get(Plot, req.plot_id)
    return {
        "village": plot.village_name if plot else "",
        "acres": M.farmer_context(plot=plot, req=req).acres,
        "service": M.SERVICE_NAMES.get(req.service_type, req.service_type),
    }


# ── Event rules ──────────────────────────────────────────────────────────
def on_event(session: Session, entity: str, entity_id: int, event: str, payload: dict, actor: str) -> None:
    handler = RULES.get((entity, event)) or (RULES.get((entity, "check:*")) if event.startswith("check:") else None)
    if handler is not None:
        handler(session, entity_id, payload, actor)


def _slot_created(session: Session, slot_id: int, payload: dict, actor: str) -> None:
    slot = session.get(Slot, slot_id)
    if slot is None:
        return
    req = session.get(Request, slot.request_id)
    machine = session.get(Machine, slot.machine_id)
    if req is None or machine is None:
        return
    with session.no_autoflush:
        earlier = (
            session.query(Slot.id)
            .filter(Slot.request_id == req.id, Slot.id != slot.id, Slot.status == "cancelled")
            .first()
        )
    queue_farmer(session, "slot_changed" if earlier else "slot_scheduled", req, slot=slot)
    if _soon(slot.service_date):
        bits = _request_bits(session, req)
        queue_driver(
            session,
            "driver_job_added",
            machine,
            f"slot:{slot.id}",
            village=bits["village"],
            acres=bits["acres"],
            seq=slot.seq,
            date=clock.fmt_en(slot.service_date),
        )


def _request_will_miss(session: Session, request_id: int, payload: dict, actor: str) -> None:
    req = session.get(Request, request_id)
    if req is None:
        return
    reason_code = payload.get("reason_code") or req.reason_code or "UNKNOWN"
    queue_farmer(session, "will_miss", req, extra_key=f":{reason_code}")
    bits = _request_bits(session, req)
    queue_staff(
        session,
        "will_miss",
        "operator",
        f"{req.id}:{reason_code}",
        url=f"/desk?request={req.id}",
        urgency="high",
        request_id=req.id,
        reason=(req.next_action or req.reason or "").strip(),
        **bits,
    )


def _request_cancelled(session: Session, request_id: int, payload: dict, actor: str) -> None:
    req = session.get(Request, request_id)
    if req is None:
        return
    queue_farmer(session, "cancelled", req)
    with session.no_autoflush:
        slot = session.query(Slot).filter_by(request_id=req.id).order_by(Slot.id.desc()).first()
    if slot is not None and _soon(slot.service_date):
        machine = session.get(Machine, slot.machine_id)
        if machine is not None:
            bits = _request_bits(session, req)
            queue_driver(
                session,
                "driver_job_removed",
                machine,
                f"slot:{slot.id}",
                village=bits["village"],
                acres=bits["acres"],
                date=clock.fmt_en(slot.service_date),
            )


def _slot_started(session: Session, slot_id: int, payload: dict, actor: str) -> None:
    slot = session.get(Slot, slot_id)
    req = session.get(Request, slot.request_id) if slot else None
    if req is not None:
        queue_farmer(session, "job_started", req, slot=slot)


def _record_created(session: Session, record_id: int, payload: dict, actor: str) -> None:
    record = session.get(ServiceRecord, record_id)
    slot = session.get(Slot, record.slot_id) if record else None
    req = session.get(Request, slot.request_id) if slot else None
    if req is not None:
        queue_farmer(session, "job_done", req, slot=slot)


def _slot_not_served(session: Session, slot_id: int, payload: dict, actor: str) -> None:
    slot = session.get(Slot, slot_id)
    req = session.get(Request, slot.request_id) if slot else None
    machine = session.get(Machine, slot.machine_id) if slot else None
    if req is None or machine is None:
        return
    queue_farmer(session, "not_served", req, slot=slot)
    bits = _request_bits(session, req)
    reason = M.NOT_SERVED_WORDS.get(slot.not_served_reason or "", slot.not_served_reason or "no reason given")
    queue_staff(
        session,
        "not_served",
        "operator",
        f"slot:{slot.id}",
        url=f"/desk?request={req.id}",
        urgency="high",
        request_id=req.id,
        slot_id=slot.id,
        machine=machine.name,
        reason=reason,
        **bits,
    )


def _slot_check(session: Session, slot_id: int, payload: dict, actor: str) -> None:
    flagged = bool(payload.get("flagged")) or bool(payload.get("flags"))
    if not flagged:
        return
    slot = session.get(Slot, slot_id)
    req = session.get(Request, slot.request_id) if slot else None
    machine = session.get(Machine, slot.machine_id) if slot else None
    if req is None or machine is None:
        return
    flags = list(payload.get("flags") or [])
    for f in slot.flags_json or []:
        if f not in flags:
            flags.append(f)
    words = ", ".join(M.FLAG_WORDS.get(f, f) for f in flags) or "evidence needs a look"
    bits = _request_bits(session, req)
    queue_staff(
        session,
        "needs_review",
        "officer",
        f"slot:{slot.id}",
        url="/officer",
        request_id=req.id,
        slot_id=slot.id,
        machine=machine.name,
        flags=words,
        village=bits["village"],
    )


def _machine_patched(session: Session, machine_id: int, payload: dict, actor: str) -> None:
    status = payload.get("status", "")
    if str(getattr(status, "value", status)).lower() != "inactive":
        return
    machine = session.get(Machine, machine_id)
    if machine is None:
        return
    stamp = clock.now_utc().strftime("%Y%m%d%H%M")
    queue_staff(
        session,
        "machine_inactive",
        "operator",
        f"{machine.id}:{stamp}",
        url="/desk",
        machine_id=machine.id,
        machine=machine.name,
    )


def _login_locked(session: Session, user_id: int, payload: dict, actor: str) -> None:
    user = session.get(UserAccount, user_id)
    if user is None:
        return
    stamp = clock.now_utc().strftime("%Y%m%d%H")
    queue_staff(
        session, "login_locked", "officer", f"{user.id}:{stamp}", url="/officer", urgency="high", username=user.username
    )


RULES = {
    ("slot", "created"): _slot_created,
    ("request", "will_miss"): _request_will_miss,
    ("request", "cancelled"): _request_cancelled,
    ("slot", "started"): _slot_started,
    ("service_record", "created"): _record_created,
    ("slot", "not_served"): _slot_not_served,
    ("slot", "check:*"): _slot_check,
    ("machine", "patched"): _machine_patched,
    ("user_account", "login_locked"): _login_locked,
}


# ── Morning job list for drivers ─────────────────────────────────────────
def queue_driver_day_plans(session: Session, today: date | None = None) -> int:
    """One push per machine with jobs today. Safe to call often: once per machine per day."""
    today = today or clock.today()
    made = 0
    for machine in session.query(Machine).filter_by(status="active").all():
        slots = (
            session.query(Slot)
            .filter(Slot.machine_id == machine.id, Slot.service_date == today, Slot.status == "scheduled")
            .order_by(Slot.seq.asc())
            .all()
        )
        if not slots:
            continue
        parts = []
        for s in slots[:4]:
            req = session.get(Request, s.request_id)
            plot = session.get(Plot, req.plot_id) if req else None
            parts.append(
                f"{s.seq}. {plot.village_name if plot else '?'} {M.farmer_context(plot=plot, req=req).acres} ac"
            )
        summary = " · ".join(parts) + (" …" if len(slots) > 4 else "")
        before = len(session.new)
        queue_driver(
            session, "driver_day_plan", machine, f"{machine.id}:{today.isoformat()}", count=len(slots), summary=summary
        )
        made += len(session.new) - before
    return made


def staff_test(session: Session) -> None:
    """Used by POST /api/notify/test (not queued: sent straight away)."""
    return None


def utcnow() -> datetime:
    return clock.now_utc()
