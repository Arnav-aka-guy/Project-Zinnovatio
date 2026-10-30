"""Voice booking routes (additive, pilot v0.3).

GET  /api/voice/script      -> the five questions, prompt texts, villages and machines
POST /api/voice/understand  -> turns a spoken or typed answer into a value plus a read-back

The audio itself is static: `web/public/audio/<pa|en>/*.mp3` plus `manifest.json`,
made by `python tasks.py voices`. These routes never touch audio.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app import clock
from app.auth import Principal, require_operator
from app.db import get_db
from app.models import Village
from app.voice import catalog
from app.voice.lexicon import MACHINES
from app.voice.understand import understand, village_entries

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
    # Language of the read-back clips. Answers in either language are understood.
    lang: Literal["pa", "en"] = "pa"

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
            {"id": "en", "speech": "en-IN", "label": "English"},
        ],
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
            }
            for s in catalog.STEPS
        ],
        "prompts": {f"prompt/{k}": {"pa": pa, "en": en} for k, (pa, en) in catalog.PROMPTS.items()},
        "villages": [{"name": v.name, "name_pa": v.name_pa or v.name} for v in villages],
        "machines": [{"id": m.id, "name_pa": m.name_pa, "name_en": m.name_en} for m in MACHINES],
    }


@router.post("/understand")
def voice_understand(
    payload: VoiceUnderstandIn,
    session: Session = Depends(get_db),
    _principal: Principal = Depends(require_operator),
):
    villages = _village_list(session) if payload.step in ("village", "confirm") else None
    context = payload.context.model_dump(exclude_none=True) if payload.context else {}
    result = understand(payload.step, payload.texts, clock.today(), villages, context, payload.lang)
    return result.as_dict()
