"""Voice booking routes (additive, pilot v0.3; Hindi and Google speech in v0.4).

GET  /api/voice/script      -> the five questions, prompt texts, villages and machines
POST /api/voice/understand  -> turns a spoken or typed answer into a value plus a read-back
POST /api/voice/transcribe  -> one spoken answer (16 kHz WAV) -> text guesses, by Google
                               Speech-to-Text (Punjabi, Hindi and English at once)

The questions are played from static clips: `web/public/audio/<pa|hi|en>/*.mp3`
plus `manifest.json`, made by `python tasks.py voices`.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app import clock
from app.auth import Principal, require_operator
from app.config import settings
from app.db import get_db
from app.errors import VaariError
from app.logging_setup import log_event
from app.models import Village
from app.voice import catalog, google
from app.voice.lexicon import MACHINE_NAMES_HI, MACHINES, MONTH_WORDS, MONTHS_HI
from app.voice.understand import understand, village_entries, village_hi

router = APIRouter(prefix="/voice", tags=["voice"])

StepName = Literal["phone", "village", "acres", "machine", "date", "confirm"]


class VoiceContext(BaseModel):
    partial_phone: str | None = Field(default=None, max_length=12)
    pending: Literal["kal"] | None = None
    confirm_step: Literal["phone", "village", "acres", "machine", "date"] | None = None


class VoiceUnderstandIn(BaseModel):
    step: StepName
    texts: list[str] = Field(min_length=1, max_length=5)
    context: VoiceContext | None = None
    # Language of the read-back clips. Answers in Punjabi, Hindi or English are understood in every mode.
    lang: Literal["pa", "hi", "en"] = "pa"

    @field_validator("texts")
    @classmethod
    def check_texts(cls, v: list[str]) -> list[str]:
        out = [t[:300] for t in v]
        if not any(t.strip() for t in out):
            raise ValueError("Say or type an answer.")
        return out


def _village_list(session: Session):
    names = [row.name for row in session.query(Village).order_by(Village.name).all()]
    return village_entries(names)


@router.get("/script")
def voice_script(
    session: Session = Depends(get_db),
    _principal: Principal = Depends(require_operator),
):
    villages = _village_list(session)
    return {
        "lang": "pa-IN",
        "languages": [
            {"id": "pa", "speech": "pa-IN", "label": "ਪੰਜਾਬੀ"},
            {"id": "hi", "speech": "hi-IN", "label": "हिंदी"},
            {"id": "en", "speech": "en-IN", "label": "English"},
        ],
        # How spoken answers become text: "google" (POST /api/voice/transcribe) or "browser".
        "speech": {"provider": settings.voice_speech, "translate": settings.voice_translate and bool(settings.google_api_key)},
        "today": clock.today().isoformat(),
        "steps": [
            {
                "id": s,
                "title_pa": catalog.STEP_TITLES[s][0],
                "title_en": catalog.STEP_TITLES[s][1],
                "ask_clip": f"prompt/ask_{s}",
                "ask_pa": catalog.PROMPTS[f"ask_{s}"][0],
                "ask_en": catalog.PROMPTS[f"ask_{s}"][1],
                "hint_pa": catalog.STEP_HINTS[s][0],
                "hint_en": catalog.STEP_HINTS[s][1],
                "title_hi": catalog.STEP_TITLES_HI[s],
                "ask_hi": catalog.PROMPTS_HI[f"ask_{s}"],
                "hint_hi": catalog.STEP_HINTS_HI[s],
            }
            for s in catalog.STEPS
        ],
        "prompts": {
            f"prompt/{k}": {"pa": pa, "en": en, "hi": catalog.PROMPTS_HI[k]} for k, (pa, en) in catalog.PROMPTS.items()
        },
        "villages": [{"name": v.name, "name_pa": v.name_pa or v.name, "name_hi": village_hi(v)} for v in villages],
        "machines": [
            {"id": m.id, "name_pa": m.name_pa, "name_en": m.name_en, "name_hi": MACHINE_NAMES_HI[m.id]} for m in MACHINES
        ],
    }


@router.post("/understand")
def voice_understand(
    payload: VoiceUnderstandIn,
    session: Session = Depends(get_db),
    _principal: Principal = Depends(require_operator),
):
    villages = _village_list(session) if payload.step in ("village", "confirm") else None
    context = payload.context.model_dump(exclude_none=True) if payload.context else {}
    today = clock.today()
    result = understand(payload.step, payload.texts, today, villages, context, payload.lang)
    out = result.as_dict()
    out["via"] = "rules"
    # Not understood: ask Google Translate for English and try once more. Never for phone numbers
    # (digits are read locally in every language, and a phone number is personal data).
    if not result.ok and payload.step != "phone" and result.error_code != "NO_SPEECH":
        english = google.translate(payload.texts)
        if english:
            second = understand(payload.step, english, today, villages, context, payload.lang)
            if second.ok:
                second.heard = payload.texts[0]
                out = second.as_dict()
                out["via"] = "translate"
                out["translated"] = english[0]
    return out


def _hints(step: str | None, session: Session) -> list[str]:
    """Words Google should expect for this question (village and machine names, units, months)."""
    if step == "village":
        out = []
        for v in _village_list(session):
            out += [v.name, v.name_pa, village_hi(v)] if v.name_pa else [v.name]
        return [h for h in out if h]
    if step == "machine":
        return [n for m in MACHINES for n in (m.name_en, m.name_pa, MACHINE_NAMES_HI[m.id])]
    if step == "acres":
        return ["ਏਕੜ", "एकड़", "acres", "ਕਿੱਲੇ", "किल्ले", "killa", "ਕਨਾਲ", "कनाल", "ਸਾਢੇ", "साढ़े", "ਸਵਾ", "सवा", "ਪੌਣੇ", "पौने"]
    if step == "date":
        months = [w for ws in MONTH_WORDS.values() for w in ws[:1]] + MONTHS_HI[1:]
        return months + ["ਅੱਜ", "आज", "ਕੱਲ੍ਹ", "कल", "ਪਰਸੋਂ", "परसों", "today", "tomorrow", "yesterday", "ਪਤਾ ਨਹੀਂ", "पता नहीं"]
    if step == "confirm":
        return ["ਹਾਂ ਜੀ", "ਨਹੀਂ", "हाँ जी", "नहीं", "yes", "no", "ਠੀਕ ਹੈ", "ठीक है"]
    return []


@router.post("/transcribe")
def voice_transcribe(
    audio: UploadFile = File(...),
    lang: Literal["pa", "hi", "en"] = Form("pa"),
    step: StepName | None = Form(None),
    session: Session = Depends(get_db),
    _principal: Principal = Depends(require_operator),
):
    """One spoken answer -> text guesses (Google Speech-to-Text). 503 when Google cannot be used: the page
    then falls back to the browser's own speech recognition, or typing."""
    if settings.voice_speech != "google" or not settings.google_api_key:
        raise VaariError("VOICE_CLOUD_OFF", "Google speech-to-text is not set up on this server.", 503,
                         details={"reason": "key_missing" if not settings.google_api_key else "off"})
    data = audio.file.read(google.MAX_AUDIO_SECONDS * google.SAMPLE_RATE * 2 + 4096)
    info = google.wav_info(data)
    if info is None or info[0] != google.SAMPLE_RATE or info[1] != 1 or info[2] != 16:
        raise VaariError("VALIDATION_ERROR", "Send 16 kHz mono 16-bit WAV audio.", 422, details={"field": "audio"})
    if info[3] < 0.2:
        return {"texts": [], "language": None, "provider": "google", "error": "no_speech"}
    started = clock.monotonic()
    res = google.transcribe(data, lang, _hints(step, session))
    # No text in the log: only whether it worked and how long it took.
    log_event("voice transcribe", event="voice_transcribe", provider="google", ok=res.ok,
              latency_ms=round((clock.monotonic() - started) * 1000), where=res.error or "")
    if not res.ok and res.error != "no_speech":
        raise VaariError("VOICE_CLOUD_FAILED", "Google speech-to-text did not answer.", 503,
                         details={"reason": res.error, "retry": res.retry})
    return {"texts": res.texts, "language": res.language, "provider": "google", "error": res.error}
