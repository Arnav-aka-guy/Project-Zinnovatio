"""Web push crypto, checked against the reference decryptor (http_ece) and a real signature check."""

import json

import http_ece
import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from app.notify import webpush


def _subscriber():
    key = ec.generate_private_key(ec.SECP256R1())
    pub = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth = b"0123456789abcdef"
    return key, webpush.b64u_encode(pub), webpush.b64u_encode(auth), auth


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    pub, priv = webpush.generate_vapid_keys()
    monkeypatch.setenv("VAARI_VAPID_PUBLIC_KEY", pub)
    monkeypatch.setenv("VAARI_VAPID_PRIVATE_KEY", priv)
    monkeypatch.setenv("VAARI_VAPID_SUBJECT", "mailto:test@example.org")
    webpush.reset_vapid_cache()
    yield
    webpush.reset_vapid_cache()


def test_reference_decryptor_reads_our_message():
    key, p256dh, auth_b64, auth = _subscriber()
    message = json.dumps({"title": "ਤੁਹਾਡੀ ਵਾਰੀ", "body": "Super Seeder 01 · 15 Nov"}, ensure_ascii=False).encode()
    body = webpush.encrypt(message, p256dh, auth_b64)
    plain = http_ece.decrypt(body, private_key=key, auth_secret=auth, version="aes128gcm")
    assert plain == message


def test_each_message_uses_fresh_keys_and_salt():
    _key, p256dh, auth_b64, _auth = _subscriber()
    a = webpush.encrypt(b"same", p256dh, auth_b64)
    b = webpush.encrypt(b"same", p256dh, auth_b64)
    assert a != b and a[:16] != b[:16]


def test_rejects_bad_subscription_keys_and_large_payloads():
    _key, p256dh, auth_b64, _auth = _subscriber()
    with pytest.raises(ValueError):
        webpush.encrypt(b"x", webpush.b64u_encode(b"\x04" + b"0" * 10), auth_b64)
    with pytest.raises(ValueError):
        webpush.encrypt(b"x" * 5000, p256dh, auth_b64)


def test_vapid_header_is_a_valid_es256_jwt():
    header = webpush.vapid_authorization("https://fcm.googleapis.com/fcm/send/abc", now=1_800_000_000)
    assert header.startswith("vapid t=")
    token, k = header[len("vapid t=") :].split(", k=")
    h, c, sig = token.split(".")
    claims = json.loads(webpush.b64u_decode(c))
    assert claims == {
        "aud": "https://fcm.googleapis.com",
        "exp": 1_800_000_000 + 43200,
        "sub": "mailto:test@example.org",
    }
    assert json.loads(webpush.b64u_decode(h)) == {"typ": "JWT", "alg": "ES256"}
    raw = webpush.b64u_decode(sig)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), webpush.b64u_decode(k))
    pub.verify(der, f"{h}.{c}".encode(), ec.ECDSA(hashes.SHA256()))  # raises if wrong


def test_send_posts_an_encrypted_message_with_push_headers():
    key, p256dh, auth_b64, auth = _subscriber()
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        seen["plain"] = http_ece.decrypt(request.content, private_key=key, auth_secret=auth, version="aes128gcm")
        return httpx.Response(201)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        res = webpush.send(
            "https://push.example.org/sub/1",
            p256dh,
            auth_b64,
            {"title": "Hi"},
            urgency="high",
            topic="slot-4",
            client=client,
        )
    assert res.ok and res.status == 201
    h = seen["headers"]
    assert h["content-encoding"] == "aes128gcm" and h["urgency"] == "high" and h["ttl"] == "86400"
    assert h["topic"] == "slot-4" and h["authorization"].startswith("vapid t=")
    assert json.loads(seen["plain"]) == {"title": "Hi"}


@pytest.mark.parametrize(
    "code,gone,retry",
    [(410, True, False), (404, True, False), (429, False, True), (503, False, True), (400, False, False)],
)
def test_send_classifies_push_service_answers(code, gone, retry):
    _key, p256dh, auth_b64, _auth = _subscriber()
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(code))) as client:
        res = webpush.send("https://push.example.org/sub/1", p256dh, auth_b64, {"t": 1}, client=client)
    assert not res.ok and res.gone is gone and res.retry is retry


def test_keys_are_made_once_and_kept(tmp_path, monkeypatch):
    monkeypatch.delenv("VAARI_VAPID_PUBLIC_KEY")
    monkeypatch.delenv("VAARI_VAPID_PRIVATE_KEY")
    monkeypatch.setenv("VAARI_DATA_DIR", str(tmp_path))
    webpush.reset_vapid_cache()
    first = webpush.vapid_keys().public_b64
    webpush.reset_vapid_cache()
    assert webpush.vapid_keys().public_b64 == first
    assert (tmp_path / "vapid.json").exists()
