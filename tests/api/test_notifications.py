"""Notifications: who is told what, and how it is delivered inside Vaari (outbox, farmer page, bell, web push).

Nothing is sent by SMS or WhatsApp."""

from __future__ import annotations

import json
from datetime import timedelta

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app import clock
from app.models import Notification, PushSubscription, Slot
from app.notify import dispatch, webpush
from tests.fixtures.synthetic_photos import TINY_JPEG

PHONE = "9876500011"
FCM = "https://fcm.googleapis.com/fcm/send/device-"


# ── helpers ──────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _defaults(monkeypatch):
    monkeypatch.setenv("VAARI_FARMER_QUIET_HOURS", "")
    monkeypatch.setenv("VAARI_DRIVER_DIGEST_HOUR", "-1")
    webpush.reset_vapid_cache()
    yield
    webpush.reset_vapid_cache()


def machine(client, h, name="SS 1", service="super_seeder"):
    return client.post(
        "/api/machines",
        json={"name": name, "type": "Super Seeder", "service_types": [service], "capacity_acres_per_day": 8},
        headers=h,
    ).json()


def request(client, h, phone=PHONE, service="super_seeder", lang="pa"):
    r = client.post(
        "/api/requests",
        json={
            "phone": phone,
            "name": "Test Farmer",
            "village": "Pind Test",
            "acres": 2.5,
            "service_type": service,
            "harvest_date": str(clock.today()),
            "consent_service": True,
            "consent_evidence": True,
            "consent_share": True,
            "language": lang,
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()


def rows(temp_db, **filters):
    with temp_db() as s:
        q = s.query(Notification)
        for k, v in filters.items():
            q = q.filter(getattr(Notification, k) == v)
        return [
            dict(
                id=n.id,
                kind=n.kind,
                audience=n.audience,
                channel=n.channel,
                status=n.status,
                reason=n.status_reason,
                body=n.body,
                title=n.title,
                attempts=n.attempts,
                provider=n.provider,
            )
            for n in q.order_by(Notification.id).all()
        ]


def run(temp_db, client=None, now=None):
    with temp_db() as s:
        return dispatch.process_due(s, now=now, client=client)


def keypair():
    key = ec.generate_private_key(ec.SECP256R1())
    pub = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return webpush.b64u_encode(pub), webpush.b64u_encode(b"0123456789abcdef")


def subscribe(client, h, n=1):
    p256dh, auth = keypair()
    body = {"endpoint": f"{FCM}{n}", "keys": {"p256dh": p256dh, "auth": auth}, "label": "Desk PC"}
    r = client.post("/api/notify/subscriptions", json=body, headers=h)
    assert r.status_code == 201, r.text
    return body


class Recorder:
    def __init__(self, status=201, body=None):
        self.calls: list[httpx.Request] = []
        self.status = status
        self.body = body or {"sid": "SM123"}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        status = self.status(request) if callable(self.status) else self.status
        return httpx.Response(status, json=self.body)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self))


def finish_job(client, h, slot_id, token):
    sh = {"X-Vaari-Slot-Token": token}
    assert (
        client.post(
            f"/api/slots/{slot_id}/start", headers=sh, files={"photo": ("a.jpg", TINY_JPEG, "image/jpeg")}
        ).status_code
        == 200
    )
    return client.post(f"/api/slots/{slot_id}/done", headers=sh, files={"photo": ("b.jpg", TINY_JPEG, "image/jpeg")})


def slot_of(client, h, rid):
    req = client.get(f"/api/requests/{rid}", headers=h).json()
    return next(s for s in client.get("/api/slots", headers=h).json() if s["id"] == req["slot"]["id"])


def farmer_token(client, h, rid):
    r = client.get(f"/api/requests/{rid}/farmer-link", headers=h)
    assert r.status_code == 200, r.text
    return r.json()["path"].rsplit("/", 1)[1]


def farmer_phone_on(client, token, n="farmer"):
    """The farmer opens their page and presses Turn on: this phone now gets Vaari alerts."""
    key = ec.generate_private_key(ec.SECP256R1())
    pub = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth = b"fedcba9876543210"
    r = client.post(f"/api/farmer/{token}/push", json={
        "endpoint": f"{FCM}{n}", "keys": {"p256dh": webpush.b64u_encode(pub), "auth": webpush.b64u_encode(auth)}})
    assert r.status_code == 201, r.text
    return key, auth


def decrypt(call, key, auth):
    import http_ece

    return json.loads(http_ece.decrypt(call.content, private_key=key, auth_secret=auth, version="aes128gcm"))


# ── rules: an event queues the right messages ────────────────────────────
def test_booking_puts_the_message_on_the_farmer_page_and_queues_phone_alerts(client, auth_headers, temp_db):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    farmer = rows(temp_db, audience="farmer")
    assert [(r["kind"], r["channel"], r["status"]) for r in farmer] == [
        ("slot_scheduled", "inapp", "delivered"),  # on the farmer's page at once
        ("slot_scheduled", "webpush", "queued"),  # and a phone alert for each phone with alerts on
    ]
    assert farmer[0]["title"].startswith("ਮਸ਼ੀਨ ਦੀ ਵਾਰੀ ਪੱਕੀ")
    assert "Pind Test" in farmer[0]["body"] and "ਸਤ ਸ੍ਰੀ ਅਕਾਲ" in farmer[0]["body"]
    assert {r["channel"] for r in rows(temp_db)} <= {"inapp", "webpush"}  # never SMS or WhatsApp
    driver = rows(temp_db, audience="driver")
    assert [(r["kind"], r["channel"]) for r in driver] == [("driver_job_added", "webpush")]
    assert driver[0]["title"] == "New job: Pind Test"
    assert client.get(f"/api/requests/{rid}", headers=auth_headers).status_code == 200


def test_english_texts_for_english_speaking_farmers():
    from types import SimpleNamespace as NS

    from app.notify import messages as M

    req = NS(acres_x100=250, service_type="super_seeder")
    plot = NS(village_name="Pind Test")
    ctx = M.farmer_context(plot=plot, req=req)
    for kind in ("will_miss", "cancelled", "not_served", "job_done"):
        en = M.farmer_text(kind, "en", ctx)
        assert en.startswith("Sat Sri Akal ji.") and "Pind Test" in en
        assert M.farmer_text(kind, "pa", ctx).startswith("ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ।")
        assert M.farmer_title(kind, "en", ctx) and M.farmer_title(kind, "pa", ctx)


def test_full_job_tells_the_farmer_started_and_done_with_the_record(client, auth_headers, temp_db):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    s = slot_of(client, auth_headers, rid)
    assert finish_job(client, auth_headers, s["id"], s["link_token"]).status_code == 200
    page = rows(temp_db, audience="farmer", channel="inapp")
    assert [r["kind"] for r in page] == ["slot_scheduled", "job_started", "job_done"]
    with temp_db() as db:
        done = db.query(Notification).filter_by(kind="job_done", channel="inapp").one()
        assert done.url.startswith("/record/")


def test_will_miss_is_told_once_to_farmer_and_operators(client, auth_headers, temp_db):
    rid = request(client, auth_headers, service="baler")["id"]  # no baler machine: will miss
    for _ in range(3):
        assert client.post("/api/schedule/run", headers=auth_headers).status_code == 200
    farmer = rows(temp_db, audience="farmer", kind="will_miss")
    staff = rows(temp_db, audience="operator", kind="will_miss")
    assert sorted(r["channel"] for r in farmer) == ["inapp", "webpush"]
    assert sorted(r["channel"] for r in staff) == ["inapp", "webpush"]
    inapp = next(r for r in staff if r["channel"] == "inapp")
    assert inapp["status"] == "delivered" and inapp["title"] == f"VR-{rid} will miss its deadline"


def test_flagged_job_alerts_officer_once(client, auth_headers, temp_db):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    s = slot_of(client, auth_headers, rid)
    finish_job(client, auth_headers, s["id"], s["link_token"])  # no code entered -> code_missing flag
    alerts = rows(temp_db, audience="officer", kind="needs_review", channel="inapp")
    assert len(alerts) == 1
    assert "never penalise" in rows(temp_db, audience="officer", kind="needs_review")[0]["body"]


def test_no_consent_no_farmer_message(client, auth_headers, temp_db):
    machine(client, auth_headers)
    r = client.post("/api/requests", json={
        "phone": PHONE, "village": "Pind Test", "acres": 2, "service_type": "super_seeder",
        "harvest_date": str(clock.today()), "consent_service": False, "consent_evidence": False,
        "consent_share": False}, headers=auth_headers)
    if r.status_code == 201:
        assert rows(temp_db, audience="farmer") == []


# ── the farmer's page and link ───────────────────────────────────────────
def test_operator_gets_one_link_per_farmer_and_the_farmer_page_shows_bookings(client, auth_headers, temp_db):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    first = client.get(f"/api/requests/{rid}/farmer-link", headers=auth_headers).json()
    again = client.get(f"/api/requests/{rid}/farmer-link", headers=auth_headers).json()
    assert first["path"] == again["path"] and first["path"].startswith("/farmer/")
    assert first["devices"] == 0
    token = first["path"].rsplit("/", 1)[1]
    page = client.get(f"/api/farmer/{token}").json()
    assert page["lang"] == "pa" and page["centre"]["phone"]
    booking = page["bookings"][0]
    assert booking["id"] == rid and booking["village"] == "Pind Test" and booking["acres"] == 2.5
    assert booking["slot"]["machine"] == "SS 1" and len(booking["slot"]["service_code"]) == 4
    assert page["unread"] == 1 and page["messages"][0]["kind"] == "slot_scheduled"
    assert PHONE not in json.dumps(page) and "Test Farmer" not in json.dumps(page)  # no phone or name on the page
    r = client.post(f"/api/farmer/{token}/read", json={"all": True})
    assert r.json() == {"updated": 1}
    assert client.get(f"/api/farmer/{token}").json()["unread"] == 0
    with temp_db() as db:
        from app.models import FarmerLink

        assert db.query(FarmerLink).one().last_opened_at is not None


def test_farmer_link_needs_operator_sign_in(client, auth_headers):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    assert client.get(f"/api/requests/{rid}/farmer-link").status_code == 401


def test_farmer_routes_refuse_unknown_expired_and_turned_off_links(client, auth_headers, temp_db):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    token = farmer_token(client, auth_headers, rid)
    for path in ("", "/manifest.webmanifest"):
        assert client.get(f"/api/farmer/not-a-token{path}").status_code == 404
    assert client.post("/api/farmer/not-a-token/read", json={"all": True}).status_code == 404
    with temp_db() as db:
        from app.models import FarmerLink

        db.query(FarmerLink).one().expires_at = clock.now_utc() - timedelta(minutes=1)
        db.commit()
    r = client.get(f"/api/farmer/{token}")
    assert r.status_code == 410 and r.json()["error_code"] == "LINK_EXPIRED"


def test_farmer_phone_gets_an_encrypted_alert_that_opens_their_page(client, auth_headers, temp_db):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    token = farmer_token(client, auth_headers, rid)
    key, auth = farmer_phone_on(client, token)
    rec = Recorder()
    run(temp_db, client=rec.client())
    farmer_calls = [c for c in rec.calls if c.url.path.endswith("farmer")]
    assert len(farmer_calls) == 1
    data = decrypt(farmer_calls[0], key, auth)
    assert data["title"].startswith("ਮਸ਼ੀਨ ਦੀ ਵਾਰੀ ਪੱਕੀ") and "Pind Test" in data["body"]
    assert data["url"] == f"/farmer/{token}" and data["lang"] == "pa"
    assert farmer_calls[0].headers["urgency"] == "high"
    assert rows(temp_db, audience="farmer", channel="webpush")[0]["status"] == "sent"
    with temp_db() as db:
        assert db.query(Slot).filter_by(request_id=rid).one().notified_at is not None
    assert client.get(f"/api/requests/{rid}/farmer-link", headers=auth_headers).json()["devices"] == 1


def test_no_farmer_phone_means_the_page_only(client, auth_headers, temp_db):
    machine(client, auth_headers)
    request(client, auth_headers)
    rec = Recorder()
    counts = run(temp_db, client=rec.client())
    assert rec.calls == []
    farmer = rows(temp_db, audience="farmer", channel="webpush")[0]
    assert (farmer["status"], farmer["reason"]) == ("skipped", "no_devices")
    assert rows(temp_db, audience="farmer", channel="inapp")[0]["status"] == "delivered"
    assert counts == {"skipped": 2}  # the farmer alert and the driver alert: nobody has turned alerts on
    assert rows(temp_db, kind="farmer_unreachable") == []  # a first booking does not alarm the desk


def test_changed_turn_with_no_farmer_phone_asks_operators_to_call(client, auth_headers, temp_db):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    run(temp_db)
    r = client.patch(f"/api/requests/{rid}", json={"acres": 3}, headers=auth_headers)  # its old turn is cancelled
    assert r.status_code == 200, r.text
    assert client.post("/api/schedule/run", headers=auth_headers).status_code == 200  # a new turn
    assert rows(temp_db, audience="farmer", kind="slot_changed", channel="inapp")
    run(temp_db)
    alert = rows(temp_db, kind="farmer_unreachable", channel="inapp")
    assert len(alert) == 1 and alert[0]["audience"] == "operator"
    assert "Please call" in alert[0]["body"]


def test_turning_the_link_off_silences_its_phones(client, auth_headers, temp_db):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    old = farmer_token(client, auth_headers, rid)
    farmer_phone_on(client, old)
    new = client.post(f"/api/requests/{rid}/farmer-link/rotate", headers=auth_headers).json()
    assert new["devices"] == 0 and new["path"] != f"/farmer/{old}"
    assert client.get(f"/api/farmer/{old}").status_code == 410
    rec = Recorder()
    run(temp_db, client=rec.client())
    assert not [c for c in rec.calls if c.url.path.endswith("farmer")]
    assert rows(temp_db, audience="farmer", channel="webpush")[0]["reason"] == "no_devices"


def test_farmer_turns_alerts_off_and_can_test(client, auth_headers, temp_db, monkeypatch):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    token = farmer_token(client, auth_headers, rid)
    farmer_phone_on(client, token)
    sent = []
    monkeypatch.setattr(webpush, "send", lambda e, p, a, payload, **kw: sent.append(payload) or webpush.PushResult(
        ok=True, status=201, gone=False, retry=False, detail=""))
    r = client.post(f"/api/farmer/{token}/push/test", json={"endpoint": f"{FCM}farmer"})
    assert r.json()["sent"] == 1 and sent[0]["title"] == "ਵਾਰੀ ਦੇ ਸੁਨੇਹੇ ਚਾਲੂ ਹਨ"
    assert client.request("DELETE", f"/api/farmer/{token}/push", json={"endpoint": f"{FCM}farmer"}).status_code == 204
    assert client.get(f"/api/farmer/{token}").json()["devices"] == 0


def test_farmer_page_installs_as_its_own_app(client, auth_headers):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    token = farmer_token(client, auth_headers, rid)
    r = client.get(f"/api/farmer/{token}/manifest.webmanifest")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/manifest+json")
    m = r.json()
    assert m["start_url"] == f"/farmer/{token}" and m["scope"] == "/farmer/" and m["display"] == "standalone"


# ── dispatch: safety rules ───────────────────────────────────────────────
def test_quiet_hours_hold_the_phone_alert_not_the_message(client, auth_headers, temp_db, monkeypatch):
    monkeypatch.setenv("VAARI_FARMER_QUIET_HOURS", "21-7")
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    farmer_phone_on(client, farmer_token(client, auth_headers, rid))
    night = clock.now_utc().replace(hour=17, minute=30, second=0, microsecond=0)  # 23:00 in India
    if night < clock.now_utc():
        night += timedelta(days=1)
    rec = Recorder()
    run(temp_db, client=rec.client(), now=night)
    assert not [c for c in rec.calls if c.url.path.endswith("farmer")]
    assert rows(temp_db, audience="farmer", channel="inapp")[0]["status"] == "delivered"
    with temp_db() as s:
        n = s.query(Notification).filter_by(audience="farmer", channel="webpush").one()
        assert n.status == "queued" and n.status_reason == "quiet_hours"
        assert n.next_attempt_at.replace(tzinfo=None) == (night + timedelta(hours=8)).replace(tzinfo=None)  # 07:00
    run(temp_db, client=rec.client(), now=night + timedelta(hours=8))
    assert len([c for c in rec.calls if c.url.path.endswith("farmer")]) == 1


def test_temporary_push_error_retries_with_backoff(client, auth_headers, temp_db):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    farmer_phone_on(client, farmer_token(client, auth_headers, rid))
    now = clock.now_utc()
    rec = Recorder(status=503)
    run(temp_db, client=rec.client(), now=now)
    with temp_db() as s:
        n = s.query(Notification).filter_by(audience="farmer", channel="webpush").one()
        assert (n.status, n.attempts) == ("queued", 1)
        assert n.next_attempt_at.replace(tzinfo=None) == (now + timedelta(seconds=30)).replace(tzinfo=None)
    t = now
    for _ in range(10):
        t += timedelta(hours=7)
        run(temp_db, client=rec.client(), now=t)
    farmer = rows(temp_db, audience="farmer", channel="webpush")[0]
    assert (farmer["status"], farmer["attempts"]) == ("failed", dispatch.MAX_ATTEMPTS)


def test_cancelled_booking_never_sends_the_old_turn(client, auth_headers, temp_db):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    key, auth = farmer_phone_on(client, farmer_token(client, auth_headers, rid))
    assert client.delete(f"/api/requests/{rid}", headers=auth_headers).status_code == 200
    rec = Recorder()
    run(temp_db, client=rec.client())
    farmer = {r["kind"]: r for r in rows(temp_db, audience="farmer", channel="webpush")}
    assert (farmer["slot_scheduled"]["status"], farmer["slot_scheduled"]["reason"]) == ("skipped", "out_of_date")
    assert farmer["cancelled"]["status"] == "sent"
    calls = [c for c in rec.calls if c.url.path.endswith("farmer")]
    assert len(calls) == 1 and decrypt(calls[0], key, auth)["title"] == "ਬੁਕਿੰਗ ਰੱਦ"
    assert rows(temp_db, kind="driver_job_removed")


def test_a_message_is_claimed_once(client, auth_headers, temp_db):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    farmer_phone_on(client, farmer_token(client, auth_headers, rid))
    rec = Recorder()
    run(temp_db, client=rec.client())
    run(temp_db, client=rec.client())
    assert len([c for c in rec.calls if c.url.path.endswith("farmer")]) == 1


# ── web push for staff and drivers ───────────────────────────────────────
def test_staff_push_reaches_subscribed_devices_and_drops_dead_ones(client, auth_headers, temp_db):
    subscribe(client, auth_headers, 1)
    subscribe(client, auth_headers, 2)
    request(client, auth_headers, service="baler")  # will miss -> operator alert
    rec = Recorder(status=lambda r: 410 if r.url.path.endswith("-2") else 201)
    run(temp_db, client=rec.client())
    push = rows(temp_db, audience="operator", channel="webpush")[0]
    assert (push["status"], push["reason"]) == ("sent", "1/2 devices")
    first = rec.calls[0]
    assert first.headers["content-encoding"] == "aes128gcm"
    assert first.headers["authorization"].startswith("vapid t=")
    assert first.headers["urgency"] == "high"
    with temp_db() as s:
        dead = s.query(PushSubscription).filter(PushSubscription.endpoint.endswith("-2")).one()
        assert dead.revoked_at is not None


def test_push_payload_is_encrypted_for_the_device(client, auth_headers, temp_db):
    import http_ece

    key = ec.generate_private_key(ec.SECP256R1())
    pub = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth = b"0123456789abcdef"
    client.post(
        "/api/notify/subscriptions",
        headers=auth_headers,
        json={"endpoint": FCM + "x", "keys": {"p256dh": webpush.b64u_encode(pub), "auth": webpush.b64u_encode(auth)}},
    )
    rid = request(client, auth_headers, service="baler")["id"]
    rec = Recorder()
    run(temp_db, client=rec.client())
    plain = http_ece.decrypt(rec.calls[0].content, private_key=key, auth_secret=auth, version="aes128gcm")
    data = json.loads(plain)
    assert data["title"] == f"VR-{rid} will miss its deadline"
    assert data["url"] == f"/desk?request={rid}"
    assert "9876" not in plain.decode()  # no farmer phone in staff alerts


def test_subscription_rejects_unknown_push_hosts_and_bad_keys(client, auth_headers):
    p256dh, auth = keypair()
    for endpoint in ("https://evil.example.com/x", "http://fcm.googleapis.com/x", "https://127.0.0.1/x"):
        r = client.post(
            "/api/notify/subscriptions",
            headers=auth_headers,
            json={"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
        )
        assert r.status_code == 422, endpoint
    r = client.post(
        "/api/notify/subscriptions",
        headers=auth_headers,
        json={"endpoint": FCM + "1", "keys": {"p256dh": "A" * 30, "auth": auth}},
    )
    assert r.status_code == 422


def test_subscriptions_need_sign_in(client):
    p256dh, auth = keypair()
    r = client.post("/api/notify/subscriptions", json={"endpoint": FCM + "1", "keys": {"p256dh": p256dh, "auth": auth}})
    assert r.status_code == 401


def test_unsubscribe(client, auth_headers, temp_db):
    body = subscribe(client, auth_headers)
    assert (
        client.request(
            "DELETE", "/api/notify/subscriptions", headers=auth_headers, json={"endpoint": body["endpoint"]}
        ).status_code
        == 204
    )
    with temp_db() as s:
        assert s.query(PushSubscription).one().revoked_at is not None


def test_driver_phone_gets_its_own_jobs_only(client, auth_headers, temp_db):
    m1 = machine(client, auth_headers, "SS 1")
    machine(client, auth_headers, "SS 2", service="baler")
    token = m1["driver_path"].rsplit("/", 1)[1]
    p256dh, auth = keypair()
    r = client.post(
        f"/api/driver/{token}/push", json={"endpoint": FCM + "drv", "keys": {"p256dh": p256dh, "auth": auth}}
    )
    assert r.status_code == 201 and r.json()["machine_id"] == m1["id"]
    request(client, auth_headers)
    rec = Recorder()
    run(temp_db, client=rec.client())
    assert [c.url.path for c in rec.calls] == ["/fcm/send/device-drv"]
    assert rows(temp_db, audience="driver")[0]["status"] == "sent"


def test_driver_push_needs_a_live_link(client, auth_headers, temp_db):
    m = machine(client, auth_headers)
    token = m["driver_path"].rsplit("/", 1)[1]
    p256dh, auth = keypair()
    assert (
        client.post(
            "/api/driver/nope/push", json={"endpoint": FCM + "1", "keys": {"p256dh": p256dh, "auth": auth}}
        ).status_code
        == 404
    )
    with temp_db() as s:
        from app.models import Machine

        s.get(Machine, m["id"]).link_revoked_at = clock.now_utc()
        s.commit()
    r = client.post(f"/api/driver/{token}/push", json={"endpoint": FCM + "1", "keys": {"p256dh": p256dh, "auth": auth}})
    assert r.status_code in (401, 403, 410)


def test_morning_job_list_once_per_machine_per_day(client, auth_headers, temp_db):
    machine(client, auth_headers)
    request(client, auth_headers)
    with temp_db() as s:
        from app.notify.rules import queue_driver_day_plans

        today = clock.today()
        # The booked slot may be for today or tomorrow; plan for its date.
        d = s.query(Slot).one().service_date
        assert queue_driver_day_plans(s, today=d) == 1
        assert queue_driver_day_plans(s, today=d) == 0
        s.commit()
        assert today
    plan = rows(temp_db, kind="driver_day_plan")
    assert len(plan) == 1 and plan[0]["title"] == "Today: 1 job"
    assert "Pind Test 2.5 ac" in plan[0]["body"]


# ── inbox, outbox, summary ───────────────────────────────────────────────
def test_inbox_unread_and_mark_read(client, auth_headers):
    request(client, auth_headers, service="baler")
    inbox = client.get("/api/notify/inbox", headers=auth_headers).json()
    assert inbox["unread"] == 1 and inbox["items"][0]["kind"] == "will_miss"
    assert inbox["items"][0]["url"].startswith("/desk?request=")
    r = client.post("/api/notify/inbox/read", headers=auth_headers, json={"ids": [inbox["items"][0]["id"]]})
    assert r.json() == {"updated": 1}
    assert client.get("/api/notify/inbox", headers=auth_headers).json()["unread"] == 0


def test_outbox_shows_farmer_alerts_and_retry(client, auth_headers, temp_db):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    farmer_phone_on(client, farmer_token(client, auth_headers, rid))
    run(temp_db, client=Recorder(status=400).client())
    items = client.get(f"/api/notify/outbox?request_id={rid}&audience=farmer", headers=auth_headers).json()["items"]
    assert [i["channel"] for i in items] == ["webpush"]  # the farmer page copy is not in the outbox
    assert items[0]["status"] == "failed" and items[0]["status_reason"] == "http 400"
    r = client.post(f"/api/notify/outbox/{items[0]['id']}/retry", headers=auth_headers)
    assert r.status_code == 200 and r.json()["status"] == "queued"
    assert client.post(f"/api/notify/outbox/{items[0]['id']}/retry", headers=auth_headers).status_code == 409
    rec = Recorder()
    run(temp_db, client=rec.client())
    assert len([c for c in rec.calls if c.url.path.endswith("farmer")]) == 1
    out = client.get(f"/api/notify/outbox?request_id={rid}&audience=farmer", headers=auth_headers).json()
    assert out["items"][0]["status"] == "sent"


def test_summary_counts(client, auth_headers, temp_db):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    farmer_phone_on(client, farmer_token(client, auth_headers, rid))
    run(temp_db, client=Recorder().client())
    s = client.get("/api/notify/summary", headers=auth_headers).json()
    assert s["delivery"] == "app"
    assert s["last_7_days"]["farmer"] == {"sent": 1}
    assert s["devices"] == {"staff": 0, "driver": 0, "farmer": 1}


def test_health_reports_notifications(client):
    data = client.get("/api/health").json()
    assert data["messaging"] == "screen+wa_link"  # the contract's old field keeps its value
    n = data["notifications"]
    assert n["delivery"] == "app" and n["farmer"] == "inapp+webpush" and n["staff"] == "inapp+webpush"
    assert "sms_provider" not in n and "whatsapp_provider" not in n
    assert len(webpush.b64u_decode(n["vapid_public_key"])) == 65


def test_test_alert_goes_to_this_device(client, auth_headers, temp_db, monkeypatch):
    body = subscribe(client, auth_headers)
    calls = []

    def fake_send(endpoint, p256dh, auth, payload, **kw):
        calls.append((endpoint, payload["title"]))
        return webpush.PushResult(ok=True, status=201, gone=False, retry=False, detail="")

    monkeypatch.setattr(webpush, "send", fake_send)
    r = client.post("/api/notify/test", headers=auth_headers, json={"endpoint": body["endpoint"]})
    assert r.json() == {"devices": 1, "sent": 1, "detail": None}
    assert calls == [(body["endpoint"], "Vaari alerts are on")]


def test_a_broken_rule_never_blocks_the_booking(client, auth_headers, temp_db, monkeypatch):
    from app.notify import rules

    def boom(*a, **k):
        raise RuntimeError("bug in a rule")

    monkeypatch.setitem(rules.RULES, ("slot", "created"), boom)
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    assert client.get(f"/api/requests/{rid}", headers=auth_headers).json()["status"] == "scheduled"


# ── roles ────────────────────────────────────────────────────────────────
def _login(client, username, password):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_each_role_sees_only_its_own_alerts(client, auth_headers, temp_db):
    from app.cli_users import create_user

    create_user("asha", "operator", "operator-password-123")
    create_user("ravi", "officer", "officer-password-456")
    op = _login(client, "asha", "operator-password-123")
    off = _login(client, "ravi", "officer-password-456")
    machine(client, auth_headers)
    request(client, auth_headers, service="baler")  # operator alert (will miss)
    rid = request(client, auth_headers, phone="9876500022")["id"]
    s = slot_of(client, auth_headers, rid)
    finish_job(client, auth_headers, s["id"], s["link_token"])  # officer alert (needs review)

    op_kinds = {i["kind"] for i in client.get("/api/notify/inbox", headers=op).json()["items"]}
    off_kinds = {i["kind"] for i in client.get("/api/notify/inbox", headers=off).json()["items"]}
    assert op_kinds == {"will_miss"} and off_kinds == {"needs_review"}
    assert client.get("/api/notify/outbox", headers=off).status_code == 403
    assert client.get("/api/notify/summary", headers=off).status_code == 200

    # An officer's device is subscribed for officer alerts only.
    p256dh, auth = keypair()
    client.post(
        "/api/notify/subscriptions",
        headers=off,
        json={"endpoint": FCM + "off", "keys": {"p256dh": p256dh, "auth": auth}},
    )
    with temp_db() as db:
        sub = db.query(PushSubscription).filter_by(endpoint=FCM + "off").one()
        assert sub.roles_json == ["officer"] and sub.user_id is not None
    rec = Recorder()
    run(temp_db, client=rec.client())
    assert {r["status"] for r in rows(temp_db, audience="officer", channel="webpush")} == {"sent"}
    assert {r["reason"] for r in rows(temp_db, audience="operator", channel="webpush")} == {"no_devices"}


def test_background_worker_sends_soon_after_commit(client, auth_headers, temp_db):
    import time

    worker = dispatch.Worker(temp_db, interval_s=30)
    dispatch._worker = worker
    worker.start()
    try:
        machine(client, auth_headers)
        request(client, auth_headers)  # the commit wakes the worker; no 30 s wait
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if rows(temp_db, audience="farmer", channel="webpush")[0]["status"] == "skipped":
                break
            time.sleep(0.05)
        assert rows(temp_db, audience="farmer", channel="webpush")[0]["reason"] == "no_devices"
        assert worker.last_run_at is not None
    finally:
        dispatch.stop_worker()


@pytest.mark.parametrize(
    ("utc_hour", "quiet"),
    [(15, False), (15.6, True), (20, True), (1.4, True), (1.6, False)],  # IST = UTC + 5:30; quiet 21:00-07:00
)
def test_quiet_hours_window(monkeypatch, utc_hour, quiet):
    monkeypatch.setenv("VAARI_FARMER_QUIET_HOURS", "21-7")
    base = clock.now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    t = base + timedelta(minutes=round(utc_hour * 60))
    assert (dispatch.quiet_until(t) is not None) is quiet


def test_machine_taken_off_alerts_operators(client, auth_headers, temp_db):
    m = machine(client, auth_headers)
    request(client, auth_headers)
    r = client.patch(f"/api/machines/{m['id']}", json={"status": "inactive"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    alert = rows(temp_db, kind="machine_inactive", channel="inapp")
    assert len(alert) == 1 and alert[0]["title"] == "SS 1 marked inactive"
    # The farmer whose turn was on that machine is told it will miss (or gets a new turn) on their page.
    kinds = {r["kind"] for r in rows(temp_db, audience="farmer", channel="inapp")}
    assert kinds & {"will_miss", "slot_changed"}


def test_locked_account_alerts_officers(client, temp_db):
    from app.cli_users import create_user

    create_user("asha", "operator", "operator-password-123")
    for _ in range(12):
        r = client.post("/api/auth/login", json={"username": "asha", "password": "wrong-password-0"})
        if r.status_code == 429:
            break
    alert = rows(temp_db, kind="login_locked", channel="inapp")
    assert len(alert) == 1 and alert[0]["audience"] == "officer" and "'asha'" in alert[0]["body"]
