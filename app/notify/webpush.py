"""Web Push: message encryption (RFC 8291, aes128gcm) and VAPID signing (RFC 8292).

No push library: about 80 lines on top of `cryptography`, so every byte that
leaves the server is ours to test. `tests/unit/test_notify_webpush.py`
decrypts our output with `http_ece` (the reference implementation used by
the Web Push authors) and verifies the VAPID signature.

Keys: VAARI_VAPID_PUBLIC_KEY / VAARI_VAPID_PRIVATE_KEY (base64url). When they
are not set, a key pair is made once and kept in `<data dir>/vapid.json`, so
subscriptions survive restarts. `python tasks.py vapid-keys` prints a pair for
`.env`.
"""

from __future__ import annotations

import base64
import json
import os
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import settings

RECORD_SIZE = 4096
MAX_PAYLOAD = RECORD_SIZE - 16 - 1 - 86  # tag, delimiter, header; push services accept 4 KB bodies


def b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64u_decode(text: str) -> bytes:
    text = text.strip()
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _public_bytes(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def encrypt(
    payload: bytes,
    ua_public_b64: str,
    auth_secret_b64: str,
    *,
    salt: bytes | None = None,
    sender_private: ec.EllipticCurvePrivateKey | None = None,
) -> bytes:
    """Encrypt one push message for one subscription (RFC 8291). Returns the request body."""
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f"push payload too large ({len(payload)} bytes)")
    ua_public = b64u_decode(ua_public_b64)
    auth_secret = b64u_decode(auth_secret_b64)
    if len(ua_public) != 65 or ua_public[0] != 0x04:
        raise ValueError("subscription p256dh is not an uncompressed P-256 point")
    if len(auth_secret) < 16:
        raise ValueError("subscription auth secret is too short")

    ua_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    as_private = sender_private or ec.generate_private_key(ec.SECP256R1())
    as_public = _public_bytes(as_private.public_key())
    ecdh_secret = as_private.exchange(ec.ECDH(), ua_key)

    ikm = _hkdf(auth_secret, ecdh_secret, b"WebPush: info\x00" + ua_public + as_public, 32)
    salt = salt or os.urandom(16)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)

    ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)  # one record, last-record delimiter
    header = salt + struct.pack("!I", RECORD_SIZE) + bytes([len(as_public)]) + as_public
    return header + ciphertext


# ── VAPID keys and signing ───────────────────────────────────────────────
@dataclass(frozen=True)
class VapidKeys:
    private: ec.EllipticCurvePrivateKey
    public_b64: str


def generate_vapid_keys() -> tuple[str, str]:
    """A new (public, private) pair, both base64url, for VAARI_VAPID_* in .env."""
    key = ec.generate_private_key(ec.SECP256R1())
    private_raw = key.private_numbers().private_value.to_bytes(32, "big")
    return b64u_encode(_public_bytes(key.public_key())), b64u_encode(private_raw)


def _load_private(private_b64: str) -> ec.EllipticCurvePrivateKey:
    raw = b64u_decode(private_b64)
    if len(raw) != 32:
        raise ValueError("VAPID private key must be 32 bytes, base64url")
    return ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())


_cached: VapidKeys | None = None


def vapid_keys() -> VapidKeys:
    """The server's VAPID key pair: from the environment, else from (or into) the data folder."""
    global _cached
    if _cached is not None:
        return _cached
    pub, priv = settings.vapid_public_key, settings.vapid_private_key
    if not (pub and priv):
        path = Path(settings.data_dir) / "vapid.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            pub, priv = data["public_key"], data["private_key"]
        else:
            pub, priv = generate_vapid_keys()
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"public_key": pub, "private_key": priv}), encoding="utf-8")
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            tmp.replace(path)
    key = _load_private(priv)
    if b64u_encode(_public_bytes(key.public_key())) != pub:
        raise ValueError("VAPID public key does not match the private key")
    _cached = VapidKeys(private=key, public_b64=pub)
    return _cached


def reset_vapid_cache() -> None:
    global _cached
    _cached = None


def vapid_subject() -> str:
    if settings.vapid_subject:
        return settings.vapid_subject
    base = settings.public_base_url
    if base.startswith("https://"):
        return base
    return "mailto:vaari-admin@example.invalid"


def vapid_authorization(endpoint: str, keys: VapidKeys | None = None, now: float | None = None) -> str:
    """The `Authorization: vapid t=..., k=...` header for one push endpoint (RFC 8292)."""
    keys = keys or vapid_keys()
    parts = urlsplit(endpoint)
    claims = {
        "aud": f"{parts.scheme}://{parts.netloc}",
        "exp": int((now if now is not None else time.time()) + 12 * 3600),
        "sub": vapid_subject(),
    }
    header = {"typ": "JWT", "alg": "ES256"}
    signing_input = (
        b64u_encode(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + b64u_encode(json.dumps(claims, separators=(",", ":")).encode())
    )
    der = keys.private.sign(signing_input.encode("ascii"), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"vapid t={signing_input}.{b64u_encode(signature)}, k={keys.public_b64}"


@dataclass
class PushResult:
    ok: bool
    status: int
    gone: bool  # the subscription no longer exists (404/410): stop using it
    retry: bool  # worth trying again later (429/5xx/network)
    detail: str = ""


def send(
    endpoint: str,
    p256dh: str,
    auth: str,
    payload: dict,
    *,
    ttl: int = 86400,
    urgency: str = "normal",
    topic: str | None = None,
    client=None,
) -> PushResult:
    """Encrypt and POST one message to a push service. `client` is an httpx.Client (tests pass a mock)."""
    import httpx

    body = encrypt(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), p256dh, auth)
    headers = {
        "Authorization": vapid_authorization(endpoint),
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": str(ttl),
        "Urgency": urgency if urgency in ("very-low", "low", "normal", "high") else "normal",
    }
    if topic:
        headers["Topic"] = topic[:32]
    own = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        res = client.post(endpoint, content=body, headers=headers)
    except httpx.HTTPError as exc:
        return PushResult(ok=False, status=0, gone=False, retry=True, detail=type(exc).__name__)
    finally:
        if own:
            client.close()
    code = res.status_code
    if 200 <= code < 300:
        return PushResult(ok=True, status=code, gone=False, retry=False)
    if code in (404, 410):
        return PushResult(ok=False, status=code, gone=True, retry=False, detail="subscription gone")
    if code == 413:
        return PushResult(ok=False, status=code, gone=False, retry=False, detail="payload too large")
    return PushResult(ok=False, status=code, gone=False, retry=code == 429 or code >= 500, detail=f"http {code}")
