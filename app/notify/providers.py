"""SMS and WhatsApp senders for farmer messages.

Every provider is a plain HTTPS call through `httpx` (already a dependency),
so no vendor SDK is needed and tests use `httpx.MockTransport`.

| Channel  | VAARI_*_PROVIDER | Needs |
| -------- | ---------------- | ----- |
| sms      | twilio           | VAARI_TWILIO_ACCOUNT_SID, VAARI_TWILIO_AUTH_TOKEN, and VAARI_TWILIO_FROM or VAARI_TWILIO_MESSAGING_SERVICE_SID |
| sms      | msg91            | VAARI_MSG91_AUTH_KEY, VAARI_MSG91_TEMPLATES (JSON: kind -> DLT-approved flow template id) |
| whatsapp | cloud            | VAARI_WHATSAPP_TOKEN, VAARI_WHATSAPP_PHONE_NUMBER_ID, VAARI_WHATSAPP_TEMPLATES (JSON: kind -> approved template name) |

`log` (the default) sends nothing: the message is kept as *simulated*.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import httpx

TIMEOUT = 15.0


@dataclass
class SendResult:
    ok: bool
    provider: str
    ref: str | None = None
    retry: bool = False  # temporary problem: try again later
    detail: str = ""
    simulated: bool = False


@dataclass
class OutgoingText:
    """One farmer message. `phone` is 10 digits; `variables` feed approved templates in order."""

    kind: str
    phone: str
    body: str
    lang: str
    variables: list[str] = field(default_factory=list)


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _templates(name: str) -> dict[str, str]:
    raw = _env(name)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except ValueError:
        return {}


def _classify(provider: str, res: httpx.Response, ref: str | None = None) -> SendResult:
    code = res.status_code
    if 200 <= code < 300:
        return SendResult(ok=True, provider=provider, ref=ref)
    # 429 and 5xx are worth retrying; other 4xx (bad number, unapproved template) are not.
    retry = code == 429 or code >= 500
    return SendResult(ok=False, provider=provider, retry=retry, detail=f"http {code}")


# ── SMS ──────────────────────────────────────────────────────────────────
def send_sms(msg: OutgoingText, provider: str, client: httpx.Client | None = None) -> SendResult:
    if provider == "log":
        return SendResult(ok=True, provider="log", simulated=True, detail="provider log")
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    try:
        if provider == "twilio":
            return _twilio_sms(msg, client)
        if provider == "msg91":
            return _msg91_sms(msg, client)
        return SendResult(ok=False, provider=provider, detail="unknown sms provider")
    except httpx.HTTPError as exc:
        return SendResult(ok=False, provider=provider, retry=True, detail=type(exc).__name__)
    finally:
        if own:
            client.close()


def _twilio_sms(msg: OutgoingText, client: httpx.Client) -> SendResult:
    sid, token = _env("VAARI_TWILIO_ACCOUNT_SID"), _env("VAARI_TWILIO_AUTH_TOKEN")
    sender, service = _env("VAARI_TWILIO_FROM"), _env("VAARI_TWILIO_MESSAGING_SERVICE_SID")
    if not (sid and token and (sender or service)):
        return SendResult(ok=False, provider="twilio", detail="twilio not configured")
    data = {"To": f"+91{msg.phone}", "Body": msg.body}
    if service:
        data["MessagingServiceSid"] = service
    else:
        data["From"] = sender
    res = client.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", data=data, auth=(sid, token))
    ref = None
    if res.status_code < 300:
        ref = res.json().get("sid")
    return _classify("twilio", res, ref)


def _msg91_sms(msg: OutgoingText, client: httpx.Client) -> SendResult:
    """MSG91 Flow API. In India every SMS text must be a DLT-registered template."""
    key = _env("VAARI_MSG91_AUTH_KEY")
    template = _templates("VAARI_MSG91_TEMPLATES").get(msg.kind)
    if not key:
        return SendResult(ok=False, provider="msg91", detail="msg91 not configured")
    if not template:
        return SendResult(ok=False, provider="msg91", detail=f"no DLT template for {msg.kind}")
    recipient = {"mobiles": f"91{msg.phone}"}
    for i, value in enumerate(msg.variables, start=1):
        recipient[f"var{i}"] = value
    res = client.post(
        "https://control.msg91.com/api/v5/flow/",
        headers={"authkey": key, "content-type": "application/json", "accept": "application/json"},
        json={"template_id": template, "short_url": "0", "recipients": [recipient]},
    )
    ref = None
    if res.status_code < 300:
        body = res.json()
        if body.get("type") == "error":
            return SendResult(ok=False, provider="msg91", detail=str(body.get("message", "error"))[:120])
        ref = body.get("request_id") or body.get("message")
    return _classify("msg91", res, ref)


# ── WhatsApp ─────────────────────────────────────────────────────────────
def send_whatsapp(msg: OutgoingText, provider: str, client: httpx.Client | None = None) -> SendResult:
    if provider == "log":
        return SendResult(ok=True, provider="log", simulated=True, detail="provider log")
    if provider != "cloud":
        return SendResult(ok=False, provider=provider, detail="unknown whatsapp provider")
    token, phone_id = _env("VAARI_WHATSAPP_TOKEN"), _env("VAARI_WHATSAPP_PHONE_NUMBER_ID")
    if not (token and phone_id):
        return SendResult(ok=False, provider="cloud", detail="whatsapp not configured")
    template = _templates("VAARI_WHATSAPP_TEMPLATES").get(msg.kind)
    if template:
        payload = {
            "messaging_product": "whatsapp",
            "to": f"91{msg.phone}",
            "type": "template",
            "template": {
                "name": template,
                "language": {"code": "pa" if msg.lang == "pa" else "en"},
                "components": [{"type": "body", "parameters": [{"type": "text", "text": v} for v in msg.variables]}],
            },
        }
    else:
        # Free text only reaches a farmer who wrote to the business in the last 24 hours.
        payload = {
            "messaging_product": "whatsapp",
            "to": f"91{msg.phone}",
            "type": "text",
            "text": {"body": msg.body, "preview_url": False},
        }
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    try:
        version = _env("VAARI_WHATSAPP_API_VERSION") or "v21.0"
        res = client.post(
            f"https://graph.facebook.com/{version}/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        ref = None
        if res.status_code < 300:
            msgs = res.json().get("messages") or [{}]
            ref = msgs[0].get("id")
        return _classify("cloud", res, ref)
    except httpx.HTTPError as exc:
        return SendResult(ok=False, provider="cloud", retry=True, detail=type(exc).__name__)
    finally:
        if own:
            client.close()
