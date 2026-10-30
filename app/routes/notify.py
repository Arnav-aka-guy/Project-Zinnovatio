"""Notifications: staff inbox, device sign-up for push alerts, and the farmer message outbox.

| Route | Who |
| ----- | --- |
| POST/DELETE /notify/subscriptions | signed-in staff: this device gets alerts for their role |
| POST/DELETE /driver/{machine_token}/push | the driver link: this phone gets job alerts |
| POST /driver/{machine_token}/push/test | the driver link |
| GET  /notify/inbox, POST /notify/inbox/read | staff (alerts for their role) |
| GET  /notify/summary | staff (counts only, no farmer details) |
| POST /notify/test | staff: a test alert to this device |
| GET  /notify/outbox, POST /notify/outbox/{id}/retry | operator (farmer, staff and driver alerts) |

Farmer pages and their alerts are in app/routes/farmer.py. Nothing is sent by SMS or WhatsApp.
"""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import clock
from app.auth import Principal, require_operator, require_staff
from app.config import settings
from app.db import get_db
from app.errors import VaariError
from app.models import Machine, Notification, PushSubscription
from app.notify import dispatch, webpush
from app.notify import messages as M
from app.tokens import require_live_link

router = APIRouter(prefix="/notify", tags=["notify"])
# Driver phones use the driver link (no sign-in), so these live under /driver like the rest of it.
driver_push_router = APIRouter(prefix="/driver", tags=["notify"])

# Push services used by Chrome/Android, Firefox, Edge/Windows and Safari/iOS.
_PUSH_HOST_SUFFIXES = (
    "fcm.googleapis.com",
    "android.googleapis.com",
    "push.services.mozilla.com",
    "notify.windows.com",
    "push.apple.com",
)


def _push_host_ok(host: str) -> bool:
    extra = tuple(h.strip().lower() for h in os.environ.get("VAARI_PUSH_HOSTS", "").split(",") if h.strip())
    host = host.lower()
    return any(host == s or host.endswith("." + s) for s in _PUSH_HOST_SUFFIXES + extra)


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=20, max_length=200)
    auth: str = Field(min_length=8, max_length=100)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2000)
    keys: SubscriptionKeys
    label: str | None = Field(None, max_length=80)


class EndpointIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2000)


class ReadIn(BaseModel):
    ids: list[int] | None = Field(None, max_length=500)
    all: bool = False


class TestIn(BaseModel):
    endpoint: str | None = Field(None, max_length=2000)


def _check_subscription(body: SubscriptionIn) -> None:
    u = urlparse(body.endpoint)
    if u.scheme != "https" or not u.hostname or not _push_host_ok(u.hostname):
        raise VaariError("INVALID_SUBSCRIPTION", "This browser's push service is not supported.", 422)
    try:
        if len(webpush.b64u_decode(body.keys.p256dh)) != 65 or len(webpush.b64u_decode(body.keys.auth)) < 16:
            raise ValueError
    except ValueError:
        raise VaariError("INVALID_SUBSCRIPTION", "The device sent broken push keys.", 422) from None


def _save_subscription(
    session: Session,
    body: SubscriptionIn,
    *,
    roles: list[str],
    user_id: int | None,
    machine_id: int | None,
    farmer_link_id: int | None = None,
) -> PushSubscription:
    _check_subscription(body)
    now = clock.now_utc()
    sub = session.query(PushSubscription).filter_by(endpoint=body.endpoint).first()
    if sub is None:
        sub = PushSubscription(endpoint=body.endpoint, created_at=now, failures=0)
        session.add(sub)
    sub.p256dh = body.keys.p256dh
    sub.auth = body.keys.auth
    sub.roles_json = roles
    sub.user_id = user_id
    sub.machine_id = machine_id
    sub.farmer_link_id = farmer_link_id
    sub.label = (body.label or "").strip() or None
    sub.revoked_at = None
    sub.failures = 0
    session.commit()
    return sub


def _sub_out(sub: PushSubscription) -> dict[str, Any]:
    return {
        "id": sub.id,
        "roles": sub.roles_json or [],
        "machine_id": sub.machine_id,
        "label": sub.label,
        "created_at": clock.iso_z(sub.created_at),
    }


def _live_machine(session: Session, token: str) -> Machine:
    machine = session.query(Machine).filter_by(link_token=token).first()
    if machine is None:
        raise VaariError("NOT_FOUND", "Machine not found.", 404)
    require_live_link(machine.link_expires_at, machine.link_revoked_at, "driver")
    return machine


def _push_now(session: Session, subs: list[PushSubscription], title: str, body: str, url: str) -> dict[str, Any]:
    """Send one alert straight away (the test buttons), so people see at once if it works."""
    now = clock.now_utc()
    payload = {
        "id": 0,
        "kind": "test",
        "title": title,
        "body": body,
        "url": url,
        "tag": "vaari-test",
        "urgency": "normal",
    }
    sent = 0
    detail = ""
    for sub in subs:
        try:
            res = webpush.send(sub.endpoint, sub.p256dh, sub.auth, payload, ttl=600)
        except Exception as exc:  # noqa: BLE001
            res = webpush.PushResult(ok=False, status=0, gone=False, retry=True, detail=type(exc).__name__)
        if res.ok:
            sent += 1
            sub.last_success_at = now
            sub.failures = 0
        else:
            detail = res.detail or f"http_{res.status}"
            if res.gone:
                sub.revoked_at = now
    session.commit()
    return {"devices": len(subs), "sent": sent, "detail": detail or None}


# ── Staff devices ────────────────────────────────────────────────────────
@router.post("/subscriptions", status_code=status.HTTP_201_CREATED)
def add_subscription(
    body: SubscriptionIn, session: Session = Depends(get_db), principal: Principal = Depends(require_staff)
) -> dict[str, Any]:
    sub = _save_subscription(session, body, roles=sorted(principal.roles), user_id=principal.user_id, machine_id=None)
    return _sub_out(sub)


@router.delete("/subscriptions", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def remove_subscription(
    body: EndpointIn, session: Session = Depends(get_db), _principal: Principal = Depends(require_staff)
) -> Response:
    sub = session.query(PushSubscription).filter_by(endpoint=body.endpoint).first()
    if sub is not None and sub.machine_id is None and sub.farmer_link_id is None and sub.revoked_at is None:
        sub.revoked_at = clock.now_utc()
        session.commit()
    return Response(status_code=204)


@router.post("/test")
def send_test(
    body: TestIn, session: Session = Depends(get_db), principal: Principal = Depends(require_staff)
) -> dict[str, Any]:
    q = session.query(PushSubscription).filter(
        PushSubscription.revoked_at.is_(None),
        PushSubscription.machine_id.is_(None),
        PushSubscription.farmer_link_id.is_(None),
    )
    subs = (
        q.filter(PushSubscription.endpoint == body.endpoint).all()
        if body.endpoint
        else [s for s in q.all() if set(s.roles_json or []) & principal.roles]
    )
    title, text = M.staff_alert("test")
    return _push_now(session, subs, title, text, "/")


# ── Driver phones ────────────────────────────────────────────────────────
@driver_push_router.post("/{machine_token}/push", status_code=status.HTTP_201_CREATED)
def add_driver_subscription(
    machine_token: str, body: SubscriptionIn, session: Session = Depends(get_db)
) -> dict[str, Any]:
    machine = _live_machine(session, machine_token)
    sub = _save_subscription(session, body, roles=[], user_id=None, machine_id=machine.id)
    return _sub_out(sub)


@driver_push_router.delete("/{machine_token}/push", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def remove_driver_subscription(machine_token: str, body: EndpointIn, session: Session = Depends(get_db)) -> Response:
    machine = _live_machine(session, machine_token)
    sub = session.query(PushSubscription).filter_by(endpoint=body.endpoint, machine_id=machine.id).first()
    if sub is not None and sub.revoked_at is None:
        sub.revoked_at = clock.now_utc()
        session.commit()
    return Response(status_code=204)


@driver_push_router.post("/{machine_token}/push/test")
def send_driver_test(machine_token: str, body: TestIn, session: Session = Depends(get_db)) -> dict[str, Any]:
    machine = _live_machine(session, machine_token)
    q = session.query(PushSubscription).filter(
        PushSubscription.revoked_at.is_(None), PushSubscription.machine_id == machine.id
    )
    if body.endpoint:
        q = q.filter(PushSubscription.endpoint == body.endpoint)
    return _push_now(
        session,
        q.all(),
        "Job alerts are on",
        f"This phone will hear about new jobs for {machine.name}.",
        f"/driver/{machine.link_token}",
    )


# ── Staff inbox ──────────────────────────────────────────────────────────
def _inbox_query(session: Session, principal: Principal):
    return session.query(Notification).filter(
        Notification.channel == "inapp", Notification.audience.in_(sorted(principal.roles))
    )


def _alert_out(n: Notification) -> dict[str, Any]:
    return {
        "id": n.id,
        "kind": n.kind,
        "audience": n.audience,
        "title": n.title or "",
        "body": n.body,
        "url": n.url or "/",
        "urgency": n.urgency,
        "request_id": n.request_id,
        "created_at": clock.iso_z(n.created_at),
        "read": n.read_at is not None,
    }


@router.get("/inbox")
def get_inbox(
    limit: int = Query(30, ge=1, le=100),
    session: Session = Depends(get_db),
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    q = _inbox_query(session, principal)
    unread = q.filter(Notification.read_at.is_(None)).count()
    items = q.order_by(Notification.id.desc()).limit(limit).all()
    return {"unread": unread, "items": [_alert_out(n) for n in items]}


@router.post("/inbox/read")
def mark_read(
    body: ReadIn, session: Session = Depends(get_db), principal: Principal = Depends(require_staff)
) -> dict[str, Any]:
    """Alerts are a shared team inbox: one person marking an alert read clears it for the team."""
    q = _inbox_query(session, principal).filter(Notification.read_at.is_(None))
    if not body.all:
        if not body.ids:
            return {"updated": 0}
        q = q.filter(Notification.id.in_(body.ids))
    now = clock.now_utc()
    rows = q.all()
    for n in rows:
        n.read_at = now
    session.commit()
    return {"updated": len(rows)}


@router.get("/summary")
def get_summary(session: Session = Depends(get_db), _principal: Principal = Depends(require_staff)) -> dict[str, Any]:
    since = clock.now_utc() - timedelta(days=7)
    rows = (
        session.query(Notification.audience, Notification.status, func.count(Notification.id))
        .filter(Notification.channel != "inapp", Notification.created_at >= dispatch._naive(since))
        .group_by(Notification.audience, Notification.status)
        .all()
    )
    by: dict[str, dict[str, int]] = {}
    for audience, st, count in rows:
        group = "farmer" if audience == "farmer" else ("driver" if audience == "driver" else "staff")
        by.setdefault(group, {})
        by[group][st] = by[group].get(st, 0) + count
    dev = {"staff": 0, "driver": 0, "farmer": 0}
    for sub in session.query(PushSubscription).filter(PushSubscription.revoked_at.is_(None)).all():
        dev["farmer" if sub.farmer_link_id else "driver" if sub.machine_id else "staff"] += 1
    worker = dispatch.current_worker()
    return {
        "delivery": "app",
        "quiet_hours": "-".join(str(h) for h in settings.farmer_quiet_hours) if settings.farmer_quiet_hours else None,
        "last_7_days": by,
        "devices": dev,
        "worker_running": worker is not None,
        "worker_last_run_at": clock.iso_z(worker.last_run_at) if worker and worker.last_run_at else None,
    }


# ── Outbox (operator only) ───────────────────────────────────────────────
def _outbox_out(n: Notification) -> dict[str, Any]:
    return {
        "id": n.id,
        "kind": n.kind,
        "audience": n.audience,
        "channel": n.channel,
        "lang": n.lang,
        "title": n.title,
        "body": n.body,
        "status": n.status,
        "status_reason": n.status_reason,
        "attempts": n.attempts,
        "provider": n.provider,
        "request_id": n.request_id,
        "slot_id": n.slot_id,
        "machine_id": n.machine_id,
        "created_at": clock.iso_z(n.created_at),
        "sent_at": clock.iso_z(n.sent_at) if n.sent_at else None,
        "next_attempt_at": clock.iso_z(n.next_attempt_at) if n.next_attempt_at else None,
    }


@router.get("/outbox")
def get_outbox(
    request_id: int | None = Query(None),
    audience: Literal["farmer", "operator", "officer", "driver"] | None = Query(None),
    status_: str | None = Query(None, alias="status", max_length=20),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db),
    _principal: Principal = Depends(require_operator),
) -> dict[str, Any]:
    q = session.query(Notification).filter(Notification.channel != "inapp")
    if request_id is not None:
        q = q.filter(Notification.request_id == request_id)
    if audience is not None:
        q = q.filter(Notification.audience == audience)
    if status_:
        q = q.filter(Notification.status == status_)
    return {"items": [_outbox_out(n) for n in q.order_by(Notification.id.desc()).limit(limit).all()]}


@router.post("/outbox/{notification_id}/retry")
def retry_outbox(
    notification_id: int, session: Session = Depends(get_db), _principal: Principal = Depends(require_operator)
) -> dict[str, Any]:
    n = session.get(Notification, notification_id)
    if n is None or n.channel == "inapp":
        raise VaariError("NOT_FOUND", "Message not found.", 404)
    if n.status not in ("failed", "skipped"):
        raise VaariError(
            "NOT_RETRYABLE", "Only failed or skipped messages can be sent again.", 409, details={"status": n.status}
        )
    n.status = "queued"
    n.status_reason = "retry_by_operator"
    n.attempts = 0
    n.next_attempt_at = clock.now_utc()
    session.commit()
    dispatch.wake_worker()
    return _outbox_out(n)
