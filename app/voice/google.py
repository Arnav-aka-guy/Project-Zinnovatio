"""Google Cloud Speech-to-Text and Translation for voice booking (optional).

Both need `VAARI_GOOGLE_API_KEY`: a Google Cloud API key whose project has
"Cloud Speech-to-Text API" and/or "Cloud Translation API" turned on. The key
stays on the server; browsers only send audio or text to Vaari.

- `transcribe()`: one spoken answer (16 kHz mono WAV) -> up to 5 guesses.
  Punjabi, Hindi and English are all tried at once (one is the main language,
  the other two are "alternative languages"), so a farmer can answer in any
  of them whatever language the questions are asked in. The village and
  machine names are sent as hints so they are heard correctly.
- `translate()`: text Vaari could not read -> English, so the English rules
  can try again. Never used for phone numbers.

Every failure comes back as a plain result with a reason, never an exception,
so the page can fall back (browser speech, typing) and say why.
Plain HTTPS through `httpx`, like the rest of Vaari: no Google SDK.
"""

from __future__ import annotations

import base64
import threading
from collections import OrderedDict
from dataclasses import dataclass, field

import httpx

from app import clock
from app.config import settings

SPEECH_URL = "https://speech.googleapis.com/v1p1beta1/speech:recognize"
TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"
TIMEOUT_S = 15.0

# Google's codes. Punjabi is "Punjabi (Gurmukhi, India)".
LANG_CODES = {"pa": "pa-Guru-IN", "hi": "hi-IN", "en": "en-IN"}
SAMPLE_RATE = 16000
MAX_AUDIO_SECONDS = 30
MAX_PHRASES = 400


def _new_client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S)


# Tests replace this with a client on httpx.MockTransport.
client_factory = _new_client


@dataclass
class SpeechResult:
    ok: bool
    texts: list[str] = field(default_factory=list)
    language: str | None = None  # the language Google heard, e.g. "hi-in"
    error: str | None = None  # no_speech | key_missing | key_invalid | api_disabled | quota | network | bad_audio | error
    retry: bool = False


# What the last call to each service said, for /api/health and the voice page.
_status_lock = threading.Lock()
_status: dict[str, dict] = {"speech": {}, "translate": {}}


def _note(service: str, ok: bool, error: str | None = None) -> None:
    with _status_lock:
        _status[service] = {"ok": ok, "error": error, "at": clock.iso_z(clock.now_utc())}


def status() -> dict:
    """Settings plus the result of the last call to each service. Never contains the key."""
    with _status_lock:
        last = {k: dict(v) for k, v in _status.items()}
    return {
        "key": bool(settings.google_api_key),
        "speech": settings.voice_speech,
        "translate": settings.voice_translate and bool(settings.google_api_key),
        "last_speech": last["speech"] or None,
        "last_translate": last["translate"] or None,
    }


def _classify(res: httpx.Response) -> tuple[str, bool]:
    """(reason, retry) for a failed Google call."""
    try:
        err = res.json().get("error", {})
    except ValueError:
        err = {}
    text = f"{err.get('message', '')} {err.get('status', '')} {res.text[:400]}".lower()
    if res.status_code == 400 and "api key not valid" in text:
        return "key_invalid", False
    if res.status_code == 403 and ("has not been used" in text or "disabled" in text or "service_disabled" in text):
        return "api_disabled", False
    if res.status_code == 403:
        return "permission", False
    if res.status_code == 429 or "resource_exhausted" in text:
        return "quota", True
    if res.status_code >= 500:
        return "google_error", True
    if res.status_code == 400:
        return "bad_audio", False
    return "error", False


# ── Speech-to-Text ───────────────────────────────────────────────────────
def wav_info(data: bytes) -> tuple[int, int, int, float] | None:
    """(sample_rate, channels, bits, seconds) of a PCM WAV file, or None if it is not one."""
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    pos = 12
    rate = channels = bits = 0
    fmt_ok = False
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt " and len(body) >= 16:
            audio_format = int.from_bytes(body[0:2], "little")
            channels = int.from_bytes(body[2:4], "little")
            rate = int.from_bytes(body[4:8], "little")
            bits = int.from_bytes(body[14:16], "little")
            fmt_ok = audio_format == 1
        elif cid == b"data" and fmt_ok and rate and channels and bits:
            seconds = len(body) / (rate * channels * bits / 8)
            return rate, channels, bits, seconds
        pos += 8 + size + (size & 1)
    return None


def _texts_from(results: list[dict]) -> list[str]:
    """Join the pieces of one answer. Guess n = the n-th guess of each piece (or its best)."""
    pieces = [r.get("alternatives") or [] for r in results]
    pieces = [p for p in pieces if p]
    if not pieces:
        return []
    most = max(len(p) for p in pieces)
    out: list[str] = []
    for n in range(min(most, 5)):
        text = " ".join((p[n] if n < len(p) else p[0]).get("transcript", "").strip() for p in pieces).strip()
        if text and text not in out:
            out.append(text)
    return out


def transcribe(wav: bytes, lang: str, phrases: list[str] | None = None,
               client: httpx.Client | None = None) -> SpeechResult:
    key = settings.google_api_key
    if not key:
        return SpeechResult(ok=False, error="key_missing")
    info = wav_info(wav)
    if info is None or info[0] != SAMPLE_RATE or info[1] != 1 or info[2] != 16:
        return SpeechResult(ok=False, error="bad_audio")
    if info[3] > MAX_AUDIO_SECONDS:
        return SpeechResult(ok=False, error="too_long")
    primary = LANG_CODES.get(lang, LANG_CODES["pa"])
    config: dict = {
        "encoding": "LINEAR16",
        "sampleRateHertz": SAMPLE_RATE,
        "audioChannelCount": 1,
        "languageCode": primary,
        "alternativeLanguageCodes": [c for c in LANG_CODES.values() if c != primary],
        "maxAlternatives": 5,
        "profanityFilter": False,
        "enableAutomaticPunctuation": False,
    }
    hints = [p for p in dict.fromkeys(phrases or []) if p and len(p) <= 100][:MAX_PHRASES]
    if hints:
        config["speechContexts"] = [{"phrases": hints, "boost": 8}]
    body = {"config": config, "audio": {"content": base64.b64encode(wav).decode("ascii")}}
    own = client is None
    client = client or client_factory()
    try:
        res = client.post(SPEECH_URL, params={"key": key}, json=body)
    except httpx.HTTPError:
        _note("speech", False, "network")
        return SpeechResult(ok=False, error="network", retry=True)
    finally:
        if own:
            client.close()
    if res.status_code != 200:
        reason, retry = _classify(res)
        _note("speech", False, reason)
        return SpeechResult(ok=False, error=reason, retry=retry)
    data = res.json()
    results = data.get("results") or []
    texts = _texts_from(results)
    _note("speech", True)
    if not texts:
        return SpeechResult(ok=False, error="no_speech")
    language = next((r.get("languageCode") for r in results if r.get("languageCode")), None)
    return SpeechResult(ok=True, texts=texts, language=(language or "").lower() or None)


# ── Translation ──────────────────────────────────────────────────────────
_cache: OrderedDict[tuple[str, ...], list[str]] = OrderedDict()
_CACHE_SIZE = 500


def translate(texts: list[str], target: str = "en", client: httpx.Client | None = None) -> list[str] | None:
    """English versions of `texts` (same order), or None if translation is off or failed."""
    key = settings.google_api_key
    if not key or not settings.voice_translate:
        return None
    q = [t.strip()[:300] for t in texts if t and t.strip()][:5]
    if not q:
        return None
    cache_key = (target, *q)
    with _status_lock:
        if cache_key in _cache:
            _cache.move_to_end(cache_key)
            return list(_cache[cache_key])
    own = client is None
    client = client or client_factory()
    try:
        res = client.post(TRANSLATE_URL, params={"key": key}, json={"q": q, "target": target, "format": "text"})
    except httpx.HTTPError:
        _note("translate", False, "network")
        return None
    finally:
        if own:
            client.close()
    if res.status_code != 200:
        _note("translate", False, _classify(res)[0])
        return None
    try:
        out = [t.get("translatedText", "") for t in res.json()["data"]["translations"]]
    except (KeyError, TypeError, ValueError):
        _note("translate", False, "error")
        return None
    _note("translate", True)
    out = [t for t in out if t.strip()]
    with _status_lock:
        _cache[cache_key] = out
        while len(_cache) > _CACHE_SIZE:
            _cache.popitem(last=False)
    return out or None


def reset_for_tests() -> None:
    with _status_lock:
        _cache.clear()
        _status["speech"] = {}
        _status["translate"] = {}
