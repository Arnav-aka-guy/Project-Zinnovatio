"""Notifications: who is told what, and how it is delivered (outbox, SMS/WhatsApp, web push)."""

from __future__ import annotations

import json
from datetime import timedelta

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app import clock
from app.models import MessageLog, Notification, PushSubscription, Slot
from app.notify import dispatch, webpush
from tests.fixtures.synthetic_photos import TINY_JPEG

PHONE = "9876500011"
FCM = "https://fcm.googleapis.com/fcm/send/device-"


# ── helpers ──────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _defaults(monkeypatch):
    monkeypatch.setenv("VAARI_FARMER_QUIET_HOURS", "")
    monkeypatch.delenv("VAARI_NOTIFY_MODE", raising=False)
    monkeypatch.delenv("VAARI_FARMER_CHANNELS", raising=False)
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


def live_twilio(monkeypatch, numbers=PHONE):
    monkeypatch.setenv("VAARI_NOTIFY_MODE", "live")
    monkeypatch.setenv("VAARI_SMS_PROVIDER", "twilio")
    monkeypatch.setenv("VAARI_TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("VAARI_TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setenv("VAARI_TWILIO_FROM", "+15550001111")
    monkeypatch.setenv("VAARI_NOTIFY_TEST_NUMBERS", numbers)


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


# ── rules: an event queues the right messages ────────────────────────────
def test_booking_queues_farmer_sms_and_driver_push(client, auth_headers, temp_db):
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    farmer = rows(temp_db, audience="farmer")
    assert [(r["kind"], r["channel"], r["status"]) for r in farmer] == [("slot_scheduled", "sms", "queued")]
    assert "Pind Test" in farmer[0]["body"] and "ਸਤ ਸ੍ਰੀ ਅਕਾਲ" in farmer[0]["body"]
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
    for kind in ("will_miss", "cancelled", "not_served"):
        en = M.farmer_text(kind, "en", ctx)
        assert en.startswith("Sat Sri Akal ji.") and "Pind Test" in en
        assert M.farmer_text(kind, "pa", ctx).startswith("ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ।")


def test_full_job_queues_started_and_done_with_record_link(client, auth_headers, temp_db, monkeypatch):
    monkeypatch.setenv("VAARI_PUBLIC_BASE_URL", "https://vaari.example.org")
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    s = slot_of(client, auth_headers, rid)
    assert finish_job(client, auth_headers, s["id"], s["link_token"]).status_code == 200
    kinds = [r["kind"] for r in rows(temp_db, audience="farmer")]
    assert kinds == ["slot_scheduled", "job_started", "job_done"]
    done = rows(temp_db, kind="job_done")[0]["body"]
    assert "https://vaari.example.org/record/" in done


def test_will_miss_is_told_once_to_farmer_and_operators(client, auth_headers, temp_db):
    rid = request(client, auth_headers, service="baler")["id"]  # no baler machine: will miss
    for _ in range(3):
        assert client.post("/api/schedule/run", headers=auth_headers).status_code == 200
    farmer = rows(temp_db, audience="farmer", kind="will_miss")
    staff = rows(temp_db, audience="operator", kind="will_miss")
    assert len(farmer) == 1
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
    r = client.post(
        "/api/requests",
        json={
            "phone": PHONE,
            "village": "Pind Test",
            "acres": 2,
            "service_type": "super_seeder",
            "harvest_date": str(clock.today()),
            "consent_service": False,
            "consent_evidence": False,
            "consent_share": False,
        },
        headers=auth_headers,
    )
    if r.status_code == 201:
        assert rows(temp_db, audience="farmer") == []


def test_mode_off_queues_no_farmer_messages(client, auth_headers, temp_db, monkeypatch):
    monkeypatch.setenv("VAARI_NOTIFY_MODE", "off")
    machine(client, auth_headers)
    request(client, auth_headers)
    assert rows(temp_db, audience="farmer") == []
    assert rows(temp_db, audience="driver")  # staff and driver alerts still work


# ── dispatch: simulate, live, safety rules ───────────────────────────────
def test_simulate_mode_records_but_sends_nothing(client, auth_headers, temp_db):
    machine(client, auth_headers)
    request(client, auth_headers)
    rec = Recorder()
    counts = run(temp_db, client=rec.client())
    assert rec.calls == []
    farmer = rows(temp_db, audience="farmer")[0]
    assert (farmer["status"], farmer["reason"]) == ("simulated", "simulate_mode")
    driver = rows(temp_db, audience="driver")[0]
    assert (driver["status"], driver["reason"]) == ("skipped", "no_devices")
    assert counts == {"simulated": 1, "skipped": 1}


def test_live_twilio_sends_sms_logs_it_and_marks_slot_notified(client, auth_headers, temp_db, monkeypatch):
    live_twilio(monkeypatch)
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    rec = Recorder()
    run(temp_db, client=rec.client())
    assert len(rec.calls) == 1
    call = rec.calls[0]
    assert call.url.host == "api.twilio.com" and "/Accounts/ACtest/Messages.json" in call.url.path
    form = dict(x.split("=", 1) for x in call.content.decode().split("&"))
    assert form["To"] == "%2B91" + PHONE
    farmer = rows(temp_db, audience="farmer")[0]
    assert (farmer["status"], farmer["provider"]) == ("sent", "twilio")
    with temp_db() as s:
        slot = s.query(Slot).filter_by(request_id=rid).one()
        assert slot.notified_at is not None
        log = s.query(MessageLog).filter_by(slot_id=slot.id).one()
        assert (log.channel, log.status, log.template) == ("sms", "sent", "slot_scheduled")


def test_live_outside_production_only_messages_test_numbers(client, auth_headers, temp_db, monkeypatch):
    live_twilio(monkeypatch, numbers="9000000000")
    machine(client, auth_headers)
    request(client, auth_headers)
    rec = Recorder()
    run(temp_db, client=rec.client())
    assert rec.calls == []
    assert rows(temp_db, audience="farmer")[0]["reason"] == "not_a_test_number"


def test_quiet_hours_wait_for_morning(client, auth_headers, temp_db, monkeypatch):
    live_twilio(monkeypatch)
    monkeypatch.setenv("VAARI_FARMER_QUIET_HOURS", "21-7")
    machine(client, auth_headers)
    request(client, auth_headers)
    night = clock.now_utc().replace(hour=17, minute=30, second=0, microsecond=0)  # 23:00 in India
    if night < clock.now_utc():
        night += timedelta(days=1)
    rec = Recorder()
    run(temp_db, client=rec.client(), now=night)
    assert rec.calls == []
    with temp_db() as s:
        n = s.query(Notification).filter_by(audience="farmer").one()
        assert n.status == "queued" and n.status_reason == "quiet_hours"
        assert n.next_attempt_at.replace(tzinfo=None) == (night + timedelta(hours=8)).replace(tzinfo=None)  # 07:00 IST
    run(temp_db, client=rec.client(), now=night + timedelta(hours=8))
    assert len(rec.calls) == 1


def test_temporary_error_retries_with_backoff_then_falls_back(client, auth_headers, temp_db, monkeypatch):
    live_twilio(monkeypatch)
    machine(client, auth_headers)
    request(client, auth_headers)
    now = clock.now_utc()
    rec = Recorder(status=503)
    run(temp_db, client=rec.client(), now=now)
    with temp_db() as s:
        n = s.query(Notification).filter_by(audience="farmer").one()
        assert (n.status, n.attempts) == ("queued", 1)
        assert n.next_attempt_at.replace(tzinfo=None) == (now + timedelta(seconds=30)).replace(tzinfo=None)
    t = now
    for _ in range(10):
        t += timedelta(hours=7)
        run(temp_db, client=rec.client(), now=t)
    farmer = rows(temp_db, audience="farmer")[0]
    assert (farmer["status"], farmer["attempts"]) == ("failed", dispatch.MAX_ATTEMPTS)
    # No other channel: the operators are asked to call the farmer.
    alert = rows(temp_db, kind="delivery_failed", channel="inapp")
    assert len(alert) == 1 and "Please call the farmer" in alert[0]["body"]


def test_rejected_whatsapp_falls_back_to_sms(client, auth_headers, temp_db, monkeypatch):
    live_twilio(monkeypatch)
    monkeypatch.setenv("VAARI_FARMER_CHANNELS", "whatsapp,sms")
    monkeypatch.setenv("VAARI_WHATSAPP_PROVIDER", "cloud")
    monkeypatch.setenv("VAARI_WHATSAPP_TOKEN", "wa-token")
    monkeypatch.setenv("VAARI_WHATSAPP_PHONE_NUMBER_ID", "1234")
    machine(client, auth_headers)
    request(client, auth_headers)
    rec = Recorder(status=lambda r: 400 if r.url.host == "graph.facebook.com" else 201)
    run(temp_db, client=rec.client())
    run(temp_db, client=rec.client())
    farmer = rows(temp_db, audience="farmer")
    assert [(r["channel"], r["status"]) for r in farmer] == [("whatsapp", "failed"), ("sms", "sent")]
    assert rows(temp_db, kind="delivery_failed") == []


def test_cancelled_booking_never_sends_the_old_slot_message(client, auth_headers, temp_db, monkeypatch):
    live_twilio(monkeypatch)
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    assert client.delete(f"/api/requests/{rid}", headers=auth_headers).status_code == 200
    rec = Recorder()
    run(temp_db, client=rec.client())
    farmer = {r["kind"]: r for r in rows(temp_db, audience="farmer")}
    assert (farmer["slot_scheduled"]["status"], farmer["slot_scheduled"]["reason"]) == ("skipped", "out_of_date")
    assert farmer["cancelled"]["status"] == "sent"
    assert len(rec.calls) == 1
    assert rows(temp_db, kind="driver_job_removed")


def test_seeded_requests_are_always_simulated(client, auth_headers, temp_db, monkeypatch):
    live_twilio(monkeypatch)
    machine(client, auth_headers)
    request(client, auth_headers)
    with temp_db() as s:
        from app.models import Request

        for r in s.query(Request).all():
            r.source = "seed"
        s.commit()
    rec = Recorder()
    run(temp_db, client=rec.client())
    assert rec.calls == []
    assert rows(temp_db, audience="farmer")[0]["reason"] == "demo_data"


def test_a_message_is_claimed_once(client, auth_headers, temp_db, monkeypatch):
    live_twilio(monkeypatch)
    machine(client, auth_headers)
    request(client, auth_headers)
    rec = Recorder()
    run(temp_db, client=rec.client())
    run(temp_db, client=rec.client())
    assert len(rec.calls) == 1


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


def test_outbox_shows_farmer_messages_and_retry(client, auth_headers, temp_db, monkeypatch):
    live_twilio(monkeypatch)
    machine(client, auth_headers)
    rid = request(client, auth_headers)["id"]
    run(temp_db, client=Recorder(status=400).client())
    items = client.get(f"/api/notify/outbox?request_id={rid}&audience=farmer", headers=auth_headers).json()["items"]
    assert items[0]["status"] == "failed" and items[0]["status_reason"] == "http 400"
    r = client.post(f"/api/notify/outbox/{items[0]['id']}/retry", headers=auth_headers)
    assert r.status_code == 200 and r.json()["status"] == "queued"
    assert client.post(f"/api/notify/outbox/{items[0]['id']}/retry", headers=auth_headers).status_code == 409
    rec = Recorder()
    run(temp_db, client=rec.client())
    assert len(rec.calls) == 1
    assert (
        client.get(f"/api/notify/outbox?request_id={rid}&audience=farmer", headers=auth_headers).json()["items"][0][
            "status"
        ]
        == "sent"
    )


def test_summary_counts(client, auth_headers, temp_db):
    machine(client, auth_headers)
    request(client, auth_headers)
    run(temp_db)
    s = client.get("/api/notify/summary", headers=auth_headers).json()
    assert s["farmer_mode"] == "simulate"
    assert s["last_7_days"]["farmer"] == {"simulated": 1}
    assert s["devices"] == {"staff": 0, "driver": 0}


def test_health_reports_notifications(client):
    data = client.get("/api/health").json()
    assert data["messaging"] == "screen+wa_link"
    n = data["notifications"]
    assert n["farmer_mode"] == "simulate" and n["staff"] == "inapp+webpush"
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
            if rows(temp_db, audience="farmer")[0]["status"] == "simulated":
                break
            time.sleep(0.05)
        assert rows(temp_db, audience="farmer")[0]["status"] == "simulated"
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
    # The farmer whose turn was on that machine is told it will miss (or gets a new turn).
    kinds = {r["kind"] for r in rows(temp_db, audience="farmer")}
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
