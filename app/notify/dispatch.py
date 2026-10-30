"""Deliver queued notifications as phone/desktop alerts from the Vaari app (web push).

Nothing is sent by SMS or WhatsApp. Farmers, staff and drivers each get
alerts on the devices where they pressed "Turn on" in Vaari; the farmer's
page and the staff bell also keep every message (the `inapp` rows).

A small background thread (`start_worker`) calls `process_due` every few
seconds. Each notification is claimed with a conditional UPDATE, so two
server processes never send the same alert twice.

Rules for a farmer's phone alert, in this order:

1. No consent to service messages -> skipped.
2. Out of date (the turn was cancelled, the request is no longer at risk...)
   -> skipped, so a farmer never gets an alert that is no longer true.
3. Quiet hours (default 21:00-07:00 local) -> the phone alert waits until
   morning. The message is already on the farmer's page.
4. No phone with alerts on -> skipped. For a changed turn the operators are
   asked to call the farmer.
5. Sent. A temporary error retries after 30 s, 2 min, 10 min, 1 h, 6 h.
"""

from __future__ import annotations

import logging
import threading
import zoneinfo
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import event, or_, update
from sqlalchemy.orm import Session

from app import clock
from app.config import settings
from app.models import Farmer, FarmerLink, Notification, Plot, PushSubscription, Request, Slot
from app.notify import webpush
from app.notify.rules import queue_driver_day_plans, queue_staff

log = logging.getLogger("vaari.notify")

BACKOFF_S = (30, 120, 600, 3600, 6 * 3600)
MAX_ATTEMPTS = len(BACKOFF_S) + 1
STUCK_AFTER = timedelta(minutes=10)
MAX_PUSH_FAILURES = 5

# Farmer messages that only make sense while their slot/request is in a given state.
_SLOT_STATES = {
    "slot_scheduled": {"scheduled"},
    "slot_changed": {"scheduled"},
    "job_started": {"in_progress", "done"},
}
_REQUEST_STATES = {"will_miss": {"will_miss"}, "cancelled": {"cancelled"}}


def _naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ── Quiet hours ──────────────────────────────────────────────────────────
def quiet_until(now: datetime) -> datetime | None:
    """If `now` is inside the farmers' quiet hours, the UTC time they end."""
    window = settings.farmer_quiet_hours
    if window is None:
        return None
    start, end = window
    tz = zoneinfo.ZoneInfo(settings.tz)
    local = _aware(now).astimezone(tz)
    h = local.hour
    inside = (start <= h or h < end) if start > end else (start <= h < end)
    if not inside:
        return None
    end_local = local.replace(hour=end, minute=0, second=0, microsecond=0)
    if end_local <= local:
        end_local += timedelta(days=1)
    return end_local.astimezone(timezone.utc)


# ── Bookkeeping helpers ──────────────────────────────────────────────────
def _finish(
    n: Notification,
    status: str,
    reason: str = "",
    *,
    now: datetime,
    provider: str | None = None,
    ref: str | None = None,
) -> None:
    n.status = status
    n.status_reason = reason or None
    n.next_attempt_at = None
    if provider:
        n.provider = provider
    if ref:
        n.provider_ref = ref
    if status in ("sent", "simulated"):
        n.sent_at = now


def _retry_later(n: Notification, reason: str, *, now: datetime) -> bool:
    """Schedule another try. Returns False when attempts are used up."""
    if n.attempts >= MAX_ATTEMPTS:
        return False
    n.status = "queued"
    n.status_reason = reason
    n.next_attempt_at = now + timedelta(seconds=BACKOFF_S[min(n.attempts - 1, len(BACKOFF_S) - 1)])
    return True


def _stale_reason(session: Session, n: Notification) -> str | None:
    if n.slot_id and n.kind in _SLOT_STATES:
        slot = session.get(Slot, n.slot_id)
        if slot is None or slot.status not in _SLOT_STATES[n.kind]:
            return "out_of_date"
    if n.kind == "driver_job_added" and n.slot_id:
        slot = session.get(Slot, n.slot_id)
        if slot is None or slot.status != "scheduled":
            return "out_of_date"
    if n.request_id and n.kind in _REQUEST_STATES and n.audience == "farmer":
        req = session.get(Request, n.request_id)
        if req is None or req.status not in _REQUEST_STATES[n.kind]:
            return "out_of_date"
    return None


# ── Staff and drivers: web push ──────────────────────────────────────────
def _live_farmer_links(session: Session, farmer_id: int) -> list[FarmerLink]:
    now = _naive(clock.now_utc())
    return [
        link
        for link in session.query(FarmerLink).filter(FarmerLink.farmer_id == farmer_id, FarmerLink.revoked_at.is_(None))
        if link.expires_at is None or _naive(link.expires_at) > now
    ]


def _subscriptions(session: Session, n: Notification) -> list[PushSubscription]:
    q = session.query(PushSubscription).filter(PushSubscription.revoked_at.is_(None))
    if n.audience == "driver":
        return q.filter(PushSubscription.machine_id == n.machine_id).all()
    if n.audience == "farmer":
        link_ids = [link.id for link in _live_farmer_links(session, n.farmer_id)] if n.farmer_id else []
        return q.filter(PushSubscription.farmer_link_id.in_(link_ids)).all() if link_ids else []
    q = q.filter(PushSubscription.machine_id.is_(None), PushSubscription.farmer_link_id.is_(None))
    return [s for s in q.all() if n.audience in (s.roles_json or [])]


def _url_for(session: Session, n: Notification) -> str:
    if n.url:
        return n.url
    if n.audience == "farmer" and n.farmer_id:
        links = _live_farmer_links(session, n.farmer_id)
        if links:
            return f"/farmer/{max(links, key=lambda x: x.id).token}"
    return "/"


def push_payload(n: Notification, url: str | None = None) -> dict:
    return {
        "id": n.id,
        "kind": n.kind,
        "audience": n.audience,
        "title": n.title or "Vaari",
        "body": n.body,
        "url": url or n.url or "/",
        "tag": f"vaari-{n.kind}-{n.request_id or n.slot_id or n.machine_id or n.id}",
        "urgency": n.urgency,
        "lang": n.lang,
    }


def _farmer_checks(session: Session, n: Notification, now: datetime) -> bool:
    """Farmer-only rules before the phone alert. False means stop (already finished or deferred)."""
    farmer = session.get(Farmer, n.farmer_id) if n.farmer_id else None
    if farmer is None or not farmer.consent_service:
        _finish(n, "skipped", "no_consent", now=now)
        return False
    wait = quiet_until(now)
    if wait is not None:
        n.status = "queued"
        n.status_reason = "quiet_hours"
        n.next_attempt_at = wait
        return False
    return True


def _farmer_unreachable(session: Session, n: Notification) -> None:
    """A changed turn that no farmer phone received: ask the operators to call."""
    if n.audience != "farmer" or n.kind != "slot_changed" or not n.request_id:
        return
    req = session.get(Request, n.request_id)
    plot = session.get(Plot, req.plot_id) if req else None
    queue_staff(
        session,
        "farmer_unreachable",
        "operator",
        f"{n.id}",
        url=f"/desk?request={n.request_id}",
        urgency="high",
        request_id=n.request_id,
        village=plot.village_name if plot else "",
    )


def _deliver_push(session: Session, n: Notification, now: datetime, client: httpx.Client | None) -> None:
    stale = _stale_reason(session, n)
    if stale:
        _finish(n, "skipped", stale, now=now)
        return
    if n.audience == "farmer" and not _farmer_checks(session, n, now):
        return
    subs = _subscriptions(session, n)
    if not subs:
        _finish(n, "skipped", "no_devices", now=now)
        _farmer_unreachable(session, n)
        return
    n.attempts += 1
    payload = push_payload(n, _url_for(session, n))
    ok = retry = 0
    last = ""
    for sub in subs:
        try:
            res = webpush.send(
                sub.endpoint,
                sub.p256dh,
                sub.auth,
                payload,
                urgency="high" if n.urgency == "high" else "normal",
                topic=payload["tag"][:32].replace("-", "")[:32],
                client=client,
            )
        except Exception as exc:  # noqa: BLE001
            res = webpush.PushResult(ok=False, status=0, gone=False, retry=True, detail=type(exc).__name__)
        if res.ok:
            ok += 1
            sub.last_success_at = now
            sub.failures = 0
        elif res.gone:
            sub.revoked_at = now
            last = "device_unsubscribed"
        else:
            # A busy push service (429/5xx) is not the device's fault; only refusals count against it.
            if not res.retry:
                sub.failures = (sub.failures or 0) + 1
                if sub.failures >= MAX_PUSH_FAILURES:
                    sub.revoked_at = now
            retry += int(res.retry)
            last = res.detail or f"http_{res.status}"
    if ok:
        _finish(n, "sent", f"{ok}/{len(subs)} devices", now=now, provider="webpush")
        if n.audience == "farmer" and n.slot_id and n.kind in ("slot_scheduled", "slot_changed"):
            slot = session.get(Slot, n.slot_id)
            if slot is not None and slot.notified_at is None:
                slot.notified_at = now
    elif retry and _retry_later(n, last, now=now):
        n.provider = "webpush"
    else:
        _finish(n, "failed", last or "no_device_accepted", now=now, provider="webpush")
        _farmer_unreachable(session, n)


# ── The loop ─────────────────────────────────────────────────────────────
def deliver(session: Session, n: Notification, now: datetime | None = None, client: httpx.Client | None = None) -> None:
    now = now or clock.now_utc()
    if n.channel == "inapp":
        if n.status != "delivered":
            _finish(n, "delivered", "", now=now)
        return
    _deliver_push(session, n, now, client)


def _claim(session: Session, n_id: int, now: datetime) -> bool:
    res = session.execute(
        update(Notification)
        .where(Notification.id == n_id, Notification.status == "queued")
        .values(status="sending", next_attempt_at=_naive(now))
        .execution_options(synchronize_session=False)
    )
    return res.rowcount == 1


def process_due(
    session: Session, now: datetime | None = None, limit: int = 50, client: httpx.Client | None = None
) -> dict[str, int]:
    """Send every notification whose time has come. Commits after each one."""
    now = now or clock.now_utc()
    # A crash mid-send leaves rows in 'sending'; give them back after a while.
    session.execute(
        update(Notification)
        .where(
            Notification.status == "sending",
            or_(Notification.next_attempt_at.is_(None), Notification.next_attempt_at <= _naive(now - STUCK_AFTER)),
        )
        .values(status="queued")
        .execution_options(synchronize_session=False)
    )
    session.commit()
    ids = [
        row[0]
        for row in session.query(Notification.id)
        .filter(Notification.status == "queued", Notification.next_attempt_at <= _naive(now))
        .order_by(Notification.next_attempt_at.asc(), Notification.id.asc())
        .limit(limit)
        .all()
    ]
    counts: dict[str, int] = {}
    for n_id in ids:
        if not _claim(session, n_id, now):
            session.rollback()
            continue
        session.commit()
        n = session.get(Notification, n_id)
        session.refresh(n)
        try:
            deliver(session, n, now=now, client=client)
        except Exception:  # noqa: BLE001
            log.exception("notify_deliver_error", extra={"fields": {"event": "notify_error"}})
            session.rollback()
            n = session.get(Notification, n_id)
            n.status = "queued"
            n.attempts = (n.attempts or 0) + 1
            if not _retry_later(n, "internal_error", now=now):
                _finish(n, "failed", "internal_error", now=now)
        if n.status == "sending":  # a handler forgot to finish: never leave it hanging
            _finish(n, "failed", "internal_error", now=now)
        counts[n.status] = counts.get(n.status, 0) + 1
        session.commit()
        # Only these keys are allowed in logs (no phones, names or text): see app/logging_setup.py.
        log.info(
            "notify",
            extra={
                "fields": {
                    "event": f"notify:{n.audience}:{n.kind}:{n.channel}",
                    "ok": n.status in ("sent", "delivered", "simulated"),
                    "where": n.status,
                    "provider": n.provider or "",
                }
            },
        )
    return counts


def maybe_queue_day_plans(session: Session, now: datetime | None = None) -> int:
    hour = settings.driver_digest_hour
    if hour < 0:
        return 0
    now = now or clock.now_utc()
    local = _aware(now).astimezone(zoneinfo.ZoneInfo(settings.tz))
    if local.hour < hour:
        return 0
    made = queue_driver_day_plans(session, today=clock.today())
    session.commit()
    return made


class Worker:
    def __init__(self, session_factory, interval_s: float | None = None):
        self.session_factory = session_factory
        self.interval_s = interval_s if interval_s is not None else settings.notify_interval_s
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._plan_day: str | None = None
        self.last_run_at: datetime | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="vaari-notify", daemon=True)
        self._thread.start()

    def wake(self) -> None:
        self._wake.set()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    def tick(self, client: httpx.Client | None = None) -> dict[str, int]:
        with self.session_factory() as session:
            today = clock.today().isoformat()
            hour = settings.driver_digest_hour
            local_hour = clock.now_utc().astimezone(zoneinfo.ZoneInfo(settings.tz)).hour
            if hour >= 0 and local_hour >= hour and self._plan_day != today:
                try:
                    maybe_queue_day_plans(session)
                    self._plan_day = today
                except Exception:  # noqa: BLE001
                    session.rollback()
                    log.exception("notify_day_plan_error", extra={"fields": {"event": "notify_error"}})
            counts = process_due(session, client=client)
        self.last_run_at = clock.now_utc()
        return counts

    def _run(self) -> None:
        with httpx.Client(timeout=15.0) as client:
            while not self._stop.is_set():
                try:
                    self.tick(client)
                except Exception:  # noqa: BLE001 - keep the loop alive
                    log.exception("notify_worker_error", extra={"fields": {"event": "notify_error"}})
                self._wake.wait(self.interval_s)
                self._wake.clear()


_worker: Worker | None = None


def start_worker(session_factory) -> Worker:
    global _worker
    if _worker is None:
        _worker = Worker(session_factory)
        _worker.start()
    return _worker


def stop_worker() -> None:
    global _worker
    if _worker is not None:
        _worker.stop()
        _worker = None


def current_worker() -> Worker | None:
    return _worker


def wake_worker() -> None:
    if _worker is not None:
        _worker.wake()


@event.listens_for(Session, "after_commit")
def _wake_after_commit(session: Session) -> None:
    if session.info.pop("vaari_notify_pending", False):
        wake_worker()


@event.listens_for(Session, "after_rollback")
def _forget_after_rollback(session: Session) -> None:
    session.info.pop("vaari_notify_pending", None)
