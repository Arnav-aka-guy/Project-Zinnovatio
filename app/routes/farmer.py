"""The farmer's own page in Vaari: bookings, messages, and phone alerts.

Farmers get every message inside Vaari, never by SMS or WhatsApp. The
operator shows the farmer a QR code (or gives the link) for their private
page, /farmer/<token>. On that page the farmer presses "Turn on" once, and
from then on their phone shows Vaari alerts like any app notification.

| Route | Who |
| ----- | --- |
| GET  /requests/{id}/farmer-link, POST /requests/{id}/farmer-link/rotate | operator |
| GET  /farmer/{token}, POST /farmer/{token}/read | the farmer link |
| POST/DELETE /farmer/{token}/push, POST /farmer/{token}/push/test | the farmer link |
| GET  /farmer/{token}/manifest.webmanifest | the farmer link (installs the page as an app) |
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import clock
from app.auth import Principal, require_operator
from app.config import settings
from app.db import get_db
from app.enums import from_x100
from app.errors import VaariError
from app.event_log import log_event
from app.models import Farmer, FarmerLink, Machine, Notification, Plot, PushSubscription, Request, ServiceRecord, Slot
from app.notify import messages as M
from app.routes.notify import EndpointIn, ReadIn, SubscriptionIn, TestIn, _push_now, _save_subscription
from app.tokens import link_state, new_token, require_live_link

operator_router = APIRouter(prefix="/requests", tags=["farmer"])
router = APIRouter(prefix="/farmer", tags=["farmer"])

PUSH_TITLE = {"pa": "ਵਾਰੀ ਦੇ ਸੁਨੇਹੇ ਚਾਲੂ ਹਨ", "en": "Vaari messages are on"}
PUSH_BODY = {
    "pa": "ਤੁਹਾਡੀ ਮਸ਼ੀਨ ਦੀ ਵਾਰੀ ਬਾਰੇ ਹਰ ਸੁਨੇਹਾ ਇਸ ਫ਼ੋਨ 'ਤੇ ਆਵੇਗਾ।",
    "en": "Every message about your machine turn will come to this phone.",
}


def live_link(session: Session, farmer_id: int) -> FarmerLink | None:
    for link in (
        session.query(FarmerLink)
        .filter(FarmerLink.farmer_id == farmer_id, FarmerLink.revoked_at.is_(None))
        .order_by(FarmerLink.id.desc())
    ):
        if link_state(link.expires_at, link.revoked_at) == "active":
            return link
    return None


def _new_link(session: Session, farmer_id: int) -> FarmerLink:
    now = clock.now_utc()
    link = FarmerLink(
        farmer_id=farmer_id,
        token=new_token(),
        created_at=now,
        expires_at=now + timedelta(days=settings.farmer_link_days),
    )
    session.add(link)
    session.flush()
    return link


def _devices(session: Session, link: FarmerLink) -> int:
    return (
        session.query(PushSubscription)
        .filter(PushSubscription.farmer_link_id == link.id, PushSubscription.revoked_at.is_(None))
        .count()
    )


def _link_out(session: Session, link: FarmerLink) -> dict[str, Any]:
    path = f"/farmer/{link.token}"
    return {
        "path": path,
        "url": f"{settings.public_base_url}{path}" if settings.public_base_url else None,
        "expires_at": clock.iso_z(link.expires_at) if link.expires_at else None,
        "last_opened_at": clock.iso_z(link.last_opened_at) if link.last_opened_at else None,
        "devices": _devices(session, link),
    }


def _request_or_404(session: Session, request_id: int) -> Request:
    req = session.get(Request, request_id)
    if req is None:
        raise VaariError("NOT_FOUND", "Request not found.", 404)
    return req


# ── Operator: the farmer's link and QR code ─────────────────────────────
@operator_router.get("/{id}/farmer-link")
def get_farmer_link(
    id: int, session: Session = Depends(get_db), _principal: Principal = Depends(require_operator)
) -> dict[str, Any]:
    """The farmer's page for this request's farmer. Made the first time it is asked for."""
    req = _request_or_404(session, id)
    link = live_link(session, req.farmer_id)
    if link is None:
        link = _new_link(session, req.farmer_id)
        log_event(session, actor="operator", entity="farmer_link", entity_id=link.id, event="created")
        session.commit()
    return _link_out(session, link)


@operator_router.post("/{id}/farmer-link/rotate")
def rotate_farmer_link(
    id: int, session: Session = Depends(get_db), _principal: Principal = Depends(require_operator)
) -> dict[str, Any]:
    """Turn off the farmer's old link (and the phones that used it) and make a new one."""
    req = _request_or_404(session, id)
    now = clock.now_utc()
    for old in session.query(FarmerLink).filter(FarmerLink.farmer_id == req.farmer_id, FarmerLink.revoked_at.is_(None)):
        old.revoked_at = now
        for sub in session.query(PushSubscription).filter(PushSubscription.farmer_link_id == old.id):
            sub.revoked_at = sub.revoked_at or now
    link = _new_link(session, req.farmer_id)
    log_event(session, actor="operator", entity="farmer_link", entity_id=link.id, event="rotated")
    session.commit()
    return _link_out(session, link)


# ── The farmer's page ────────────────────────────────────────────────────
def _farmer_link_or_error(session: Session, token: str) -> FarmerLink:
    link = session.query(FarmerLink).filter_by(token=token).first()
    if link is None:
        raise VaariError("NOT_FOUND", "This link is not known. Ask the centre for your link.", 404)
    require_live_link(link.expires_at, link.revoked_at, "farmer")
    return link


def _booking_out(session: Session, req: Request) -> dict[str, Any]:
    plot = session.get(Plot, req.plot_id)
    slot = (
        session.query(Slot)
        .filter(Slot.request_id == req.id, Slot.status != "cancelled")
        .order_by(Slot.id.desc())
        .first()
    )
    machine = session.get(Machine, slot.machine_id) if slot else None
    record_path = None
    if slot is not None and slot.status == "done":
        record = session.query(ServiceRecord).filter_by(slot_id=slot.id).first()
        if record is not None and link_state(record.token_expires_at, record.token_revoked_at) == "active":
            record_path = f"/record/{record.token}"
    return {
        "id": req.id,
        "village": plot.village_name if plot else "",
        "acres": from_x100(req.acres_x100),
        "service_type": req.service_type,
        "service_name": M.SERVICE_NAMES.get(req.service_type, req.service_type),
        "status": req.status,
        "deadline_date": str(req.deadline_date) if req.deadline_date else None,
        "slot": None
        if slot is None
        else {
            "service_date": str(slot.service_date),
            "machine": machine.name if machine else "",
            "seq": slot.seq,
            "status": slot.status,
            # The code the farmer tells the driver when the work is done (their own page only).
            "service_code": slot.service_code if slot.status in ("scheduled", "in_progress") else None,
        },
        "record_path": record_path,
    }


def _message_out(n: Notification) -> dict[str, Any]:
    return {
        "id": n.id,
        "kind": n.kind,
        "title": n.title or "",
        "body": n.body,
        "url": n.url,
        "request_id": n.request_id,
        "created_at": clock.iso_z(n.created_at),
        "read": n.read_at is not None,
    }


@router.get("/{token}")
def get_farmer_page(token: str, session: Session = Depends(get_db)) -> dict[str, Any]:
    link = _farmer_link_or_error(session, token)
    farmer = session.get(Farmer, link.farmer_id)
    link.last_opened_at = clock.now_utc()
    bookings = (
        session.query(Request).filter(Request.farmer_id == link.farmer_id).order_by(Request.id.desc()).limit(20).all()
    )
    msgs_q = session.query(Notification).filter(
        Notification.audience == "farmer", Notification.channel == "inapp", Notification.farmer_id == link.farmer_id
    )
    unread = msgs_q.filter(Notification.read_at.is_(None)).count()
    messages = msgs_q.order_by(Notification.id.desc()).limit(30).all()
    out = {
        "lang": "pa" if (farmer.language if farmer else "pa") == "pa" else "en",
        "centre": {"name": settings.centre_name, "phone": settings.centre_phone},
        "bookings": [_booking_out(session, r) for r in bookings],
        "messages": [_message_out(n) for n in messages],
        "unread": unread,
        "devices": _devices(session, link),
        "expires_at": clock.iso_z(link.expires_at) if link.expires_at else None,
    }
    session.commit()
    return out


@router.post("/{token}/read")
def mark_farmer_read(token: str, body: ReadIn, session: Session = Depends(get_db)) -> dict[str, Any]:
    link = _farmer_link_or_error(session, token)
    q = session.query(Notification).filter(
        Notification.audience == "farmer",
        Notification.channel == "inapp",
        Notification.farmer_id == link.farmer_id,
        Notification.read_at.is_(None),
    )
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


@router.post("/{token}/push", status_code=status.HTTP_201_CREATED)
def add_farmer_push(token: str, body: SubscriptionIn, session: Session = Depends(get_db)) -> dict[str, Any]:
    link = _farmer_link_or_error(session, token)
    sub = _save_subscription(session, body, roles=[], user_id=None, machine_id=None, farmer_link_id=link.id)
    return {"id": sub.id, "devices": _devices(session, link)}


@router.delete("/{token}/push", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def remove_farmer_push(token: str, body: EndpointIn, session: Session = Depends(get_db)) -> Response:
    link = _farmer_link_or_error(session, token)
    sub = session.query(PushSubscription).filter_by(endpoint=body.endpoint, farmer_link_id=link.id).first()
    if sub is not None and sub.revoked_at is None:
        sub.revoked_at = clock.now_utc()
        session.commit()
    return Response(status_code=204)


@router.post("/{token}/push/test")
def send_farmer_test(token: str, body: TestIn, session: Session = Depends(get_db)) -> dict[str, Any]:
    link = _farmer_link_or_error(session, token)
    farmer = session.get(Farmer, link.farmer_id)
    lang = "pa" if (farmer.language if farmer else "pa") == "pa" else "en"
    q = session.query(PushSubscription).filter(
        PushSubscription.revoked_at.is_(None), PushSubscription.farmer_link_id == link.id
    )
    if body.endpoint:
        q = q.filter(PushSubscription.endpoint == body.endpoint)
    return _push_now(session, q.all(), PUSH_TITLE[lang], PUSH_BODY[lang], f"/farmer/{link.token}")


@router.get("/{token}/manifest.webmanifest")
def get_farmer_manifest(token: str, session: Session = Depends(get_db)) -> JSONResponse:
    """Lets the farmer add their page to the home screen: it opens straight to their bookings."""
    link = _farmer_link_or_error(session, token)
    return JSONResponse(
        {
            "name": "Vaari · ਵਾਰੀ",
            "short_name": "Vaari",
            "start_url": f"/farmer/{link.token}",
            "scope": "/farmer/",
            "display": "standalone",
            "background_color": "#f8fafc",
            "theme_color": "#15803d",
            "icons": [
                {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
                {"src": "/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            ],
        },
        media_type="application/manifest+json",
    )
