"""Voice booking conversation API endpoints (Step V6).

Provides:
  - POST /api/voice/session : Initiate a voice booking session
  - POST /api/voice/consent : Record farmer consent & ask first question
  - POST /api/voice/turn    : Upload audio turn, transcribe & extract fields
  - POST /api/voice/answer  : Answer confirmation Yes/No
  - GET  /api/voice/reply/{reply_key}.wav : Fetch spoken audio prompt

Privacy & Security:
  - Audio files are processed in memory and dropped immediately.
  - Sessions expire after 30 minutes of inactivity and are evicted.
  - No PII, audio bytes, or transcripts are emitted in server logs.
"""

import datetime
import struct
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import clock
from app.db import get_db
from app.enums import RequestSource, RequestStatus, ServiceType
from app.models import Slot
from app.routes.requests import create_request_record
from app.schemas import RequestIn
from app.voice.engine import VoiceServiceUnavailable, get_voice_engine
from app.voice.replies import REPLIES, get_reply
from app.voice.understand import understand_voice_turn

router = APIRouter(prefix="/voice", tags=["voice"])

SESSION_TIMEOUT_SECONDS = 1800.0  # 30 minutes


@dataclass
class VoiceSession:
    session_id: str
    created_at: float
    last_active: float
    state: str = "idle"  # idle | consented | listening | confirming | confirmed | cancelled | needs_info
    current_field: str = "phone"
    retries: Dict[str, int] = field(default_factory=lambda: {"phone": 0, "village": 0, "acres": 0, "machine": 0, "harvest_date": 0, "confirm": 0})
    collected_fields: Dict[str, Any] = field(default_factory=dict)
    prompt_key: str = "greeting"
    last_transcript: Optional[str] = None
    request_id: Optional[str] = None
    slot_assigned: Optional[bool] = None
    slot_date: Optional[str] = None
    will_miss_reason: Optional[str] = None


class SessionStore:
    def __init__(self):
        self._sessions: Dict[str, VoiceSession] = {}
        self._lock = threading.Lock()

    def _evict_expired(self):
        now = time.monotonic()
        expired = [sid for sid, s in self._sessions.items() if now - s.last_active > SESSION_TIMEOUT_SECONDS]
        for sid in expired:
            self._sessions.pop(sid, None)

    def create(self) -> VoiceSession:
        now = time.monotonic()
        with self._lock:
            self._evict_expired()
            sid = str(uuid.uuid4())
            sess = VoiceSession(
                session_id=sid,
                created_at=now,
                last_active=now,
                state="idle",
                prompt_key="greeting",
            )
            self._sessions[sid] = sess
            return sess

    def get(self, session_id: str) -> Optional[VoiceSession]:
        now = time.monotonic()
        with self._lock:
            self._evict_expired()
            sess = self._sessions.get(session_id)
            if sess:
                sess.last_active = now
            return sess

    def remove(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()


sessions = SessionStore()


# --- Pydantic Schemas ---------------------------------------------------------

class VoiceConsentIn(BaseModel):
    session_id: str


class VoiceAnswerIn(BaseModel):
    session_id: str
    answer: str  # 'yes' | 'no'


class VoiceFieldsOut(BaseModel):
    phone: Optional[str] = None
    village: Optional[str] = None
    acres: Optional[float] = None
    machine: Optional[str] = None
    harvest_date: Optional[str] = None


class VoicePromptOut(BaseModel):
    key: str
    text_pa: str
    text_en: str
    audio_url: str


class VoiceSessionOut(BaseModel):
    session_id: str
    state: str
    current_field: Optional[str] = None
    collected_fields: VoiceFieldsOut
    prompt: VoicePromptOut
    transcript: Optional[str] = None
    request_id: Optional[str] = None
    slot_assigned: Optional[bool] = None
    slot_date: Optional[str] = None
    will_miss_reason: Optional[str] = None


def serialize_session(sess: VoiceSession) -> VoiceSessionOut:
    prompt_info = get_reply(sess.prompt_key)
    return VoiceSessionOut(
        session_id=sess.session_id,
        state=sess.state,
        current_field=sess.current_field,
        collected_fields=VoiceFieldsOut(
            phone=sess.collected_fields.get("phone"),
            village=sess.collected_fields.get("village"),
            acres=sess.collected_fields.get("acres"),
            machine=sess.collected_fields.get("machine"),
            harvest_date=sess.collected_fields.get("harvest_date"),
        ),
        prompt=VoicePromptOut(
            key=sess.prompt_key,
            text_pa=prompt_info["text_pa"],
            text_en=prompt_info["text_en"],
            audio_url=prompt_info["audio_url"],
        ),
        transcript=sess.last_transcript,
        request_id=sess.request_id,
        slot_assigned=sess.slot_assigned,
        slot_date=sess.slot_date,
        will_miss_reason=sess.will_miss_reason,
    )


# --- Endpoints ----------------------------------------------------------------

@router.post("/session", response_model=VoiceSessionOut)
def start_voice_session():
    """Start a fresh voice booking session."""
    sess = sessions.create()
    return serialize_session(sess)


@router.post("/consent", response_model=VoiceSessionOut)
def submit_voice_consent(payload: VoiceConsentIn):
    """Register farmer consent and transition to first question."""
    sess = sessions.get(payload.session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    sess.state = "consented"
    sess.current_field = "phone"
    sess.prompt_key = "ask_phone"
    return serialize_session(sess)


FIELD_ORDER = ["phone", "village", "acres", "machine", "harvest_date"]


def find_next_missing_field(collected: Dict[str, Any]) -> Optional[str]:
    for f in FIELD_ORDER:
        if f not in collected:
            return f
    return None


@router.post("/turn", response_model=VoiceSessionOut)
async def process_voice_turn(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Process farmer spoken turn."""
    sess = sessions.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Read uploaded bytes (cap at 2 MB)
    wav_bytes = await audio.read()
    if len(wav_bytes) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file exceeds 2 MB limit")
    if len(wav_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio recording")

    # Verify duration from WAV header if possible (15 seconds cap)
    if len(wav_bytes) >= 44 and wav_bytes[:4] == b"RIFF":
        try:
            byte_rate = struct.unpack("<I", wav_bytes[28:32])[0]
            data_size = struct.unpack("<I", wav_bytes[40:44])[0]
            if byte_rate > 0:
                duration_s = data_size / byte_rate
                if duration_s > 15.0:
                    raise HTTPException(status_code=400, detail="Audio exceeds 15-second cap")
        except (struct.error, IndexError):
            pass

    engine = get_voice_engine()
    try:
        transcript, _ = engine.transcribe(wav_bytes)
    except VoiceServiceUnavailable:
        sess.prompt_key = "service_down"
        return serialize_session(sess)
    finally:
        # Immediately discard audio bytes from memory
        del wav_bytes

    sess.last_transcript = transcript

    # If currently in confirming state, evaluate confirmation intent
    if sess.state == "confirming":
        understanding = understand_voice_turn(transcript, expected_field="confirm", base_date=clock.today())
        if understanding.confirmation is True:
            return confirm_booking(sess, db)
        elif understanding.confirmation is False:
            sess.state = "cancelled"
            sess.prompt_key = "cancelled"
            return serialize_session(sess)
        else:
            sess.retries["confirm"] += 1
            sess.prompt_key = "ask_confirm"
            return serialize_session(sess)

    # State is consented or listening: extract fields
    sess.state = "listening"
    understanding = understand_voice_turn(
        transcript,
        expected_field=sess.current_field,
        base_date=clock.today(),
    )

    # Capture extracted values
    captured_current = False
    if sess.current_field == "phone" and understanding.phone:
        sess.collected_fields["phone"] = understanding.phone
        captured_current = True
    elif sess.current_field == "village" and understanding.village:
        sess.collected_fields["village"] = understanding.village
        captured_current = True
    elif sess.current_field == "acres" and understanding.acres is not None:
        sess.collected_fields["acres"] = understanding.acres
        captured_current = True
    elif sess.current_field == "machine" and understanding.machine:
        sess.collected_fields["machine"] = understanding.machine
        captured_current = True
    elif sess.current_field == "harvest_date" and understanding.harvest_date:
        sess.collected_fields["harvest_date"] = understanding.harvest_date
        captured_current = True

    # Opportunistically capture any other detected fields
    if understanding.phone and "phone" not in sess.collected_fields:
        sess.collected_fields["phone"] = understanding.phone
    if understanding.village and "village" not in sess.collected_fields:
        sess.collected_fields["village"] = understanding.village
    if understanding.acres is not None and "acres" not in sess.collected_fields:
        sess.collected_fields["acres"] = understanding.acres
    if understanding.machine and "machine" not in sess.collected_fields:
        sess.collected_fields["machine"] = understanding.machine
    if understanding.harvest_date and "harvest_date" not in sess.collected_fields:
        sess.collected_fields["harvest_date"] = understanding.harvest_date

    if captured_current:
        # Reset retry counter for current field
        sess.retries[sess.current_field] = 0
        next_field = find_next_missing_field(sess.collected_fields)
        if next_field is None:
            sess.state = "confirming"
            sess.current_field = "confirm"
            sess.prompt_key = "ask_confirm"
        else:
            sess.current_field = next_field
            sess.prompt_key = f"ask_{next_field}"
    else:
        # Field was not understood
        current_retries = sess.retries.get(sess.current_field, 0) + 1
        sess.retries[sess.current_field] = current_retries

        if current_retries >= 2:
            # 2-strikes rule: If phone is known, save partial details as needs_info
            if "phone" in sess.collected_fields:
                sess.state = "needs_info"
                sess.prompt_key = "will_call_you"
                # Save partial request to DB as needs_info
                save_partial_needs_info(sess, db)
            else:
                # Save nothing if phone number is missing
                sess.state = "cancelled"
                sess.prompt_key = "will_call_you"
        else:
            # First retry
            sess.prompt_key = "did_not_understand"

    return serialize_session(sess)


@router.post("/answer", response_model=VoiceSessionOut)
def answer_voice_confirmation(payload: VoiceAnswerIn, db: Session = Depends(get_db)):
    """Handle explicit Yes/No button taps for confirmation."""
    sess = sessions.get(payload.session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    ans = payload.answer.lower().strip()
    if ans in ("yes", "haan", "y"):
        return confirm_booking(sess, db)
    elif ans in ("no", "nahin", "n"):
        sess.state = "cancelled"
        sess.prompt_key = "cancelled"
        return serialize_session(sess)

    sess.prompt_key = "ask_confirm"
    return serialize_session(sess)


def save_partial_needs_info(sess: VoiceSession, db: Session) -> None:
    """Save partial booking details as a needs_info request when phone is known."""
    phone = sess.collected_fields.get("phone")
    if not phone:
        return

    service_type = map_machine_to_service_type(sess.collected_fields.get("machine"))
    village_name = sess.collected_fields.get("village") or "Nabha"
    acres_val = float(sess.collected_fields.get("acres") or 5.0)

    harvest_d = None
    if sess.collected_fields.get("harvest_date"):
        try:
            harvest_d = datetime.date.fromisoformat(sess.collected_fields["harvest_date"])
        except ValueError:
            pass

    req_in = RequestIn(
        phone=phone,
        village=village_name,
        acres=acres_val,
        service_type=service_type,
        harvest_date=harvest_d,
        consent_service=True,
        consent_evidence=True,
        consent_share=True,
    )

    try:
        req = create_request_record(
            session=db,
            payload=req_in,
            source=RequestSource.VOICE,
            run_scheduler=False,
        )
        req.status = RequestStatus.NEEDS_INFO
        req.reason = "Voice booking incomplete after retries; centre to call farmer."
        db.commit()
        sess.request_id = str(req.id)
    except Exception:
        db.rollback()


def confirm_booking(sess: VoiceSession, db: Session) -> VoiceSessionOut:
    """Commit verified booking details into SQLite database and schedule."""
    phone = sess.collected_fields.get("phone", "9876543210")
    village_name = sess.collected_fields.get("village", "Nabha")
    acres_val = float(sess.collected_fields.get("acres", 5.0))
    service_type = map_machine_to_service_type(sess.collected_fields.get("machine"))

    harvest_d = None
    if sess.collected_fields.get("harvest_date"):
        try:
            harvest_d = datetime.date.fromisoformat(sess.collected_fields["harvest_date"])
        except ValueError:
            harvest_d = clock.today()
    else:
        harvest_d = clock.today()

    req_in = RequestIn(
        phone=phone,
        village=village_name,
        acres=acres_val,
        service_type=service_type,
        harvest_date=harvest_d,
        consent_service=True,
        consent_evidence=True,
        consent_share=True,
    )

    try:
        req = create_request_record(
            session=db,
            payload=req_in,
            source=RequestSource.VOICE,
            run_scheduler=True,
        )
        db.commit()
        db.refresh(req)

        sess.request_id = str(req.id)
        sess.state = "confirmed"

        if req.status == RequestStatus.SCHEDULED:
            slot = db.query(Slot).filter_by(request_id=req.id).first()
            sess.slot_assigned = True
            sess.slot_date = str(slot.service_date) if slot else str(req.harvest_date)
            sess.prompt_key = "confirmed_with_date"
        elif req.status == RequestStatus.WILL_MISS:
            sess.slot_assigned = False
            sess.will_miss_reason = req.reason or "No slot available"
            sess.prompt_key = "no_slot_will_miss"
        else:
            sess.slot_assigned = False
            sess.prompt_key = "confirmed_needs_info"

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Booking creation failed: {e}") from None

    return serialize_session(sess)


def map_machine_to_service_type(machine_name: Optional[str]) -> ServiceType:
    if not machine_name:
        return ServiceType.SUPER_SEEDER
    m = machine_name.lower()
    if "happy" in m:
        return ServiceType.HAPPY_SEEDER
    elif "baler" in m:
        return ServiceType.BALER
    elif "mulcher" in m:
        return ServiceType.MULCHER
    return ServiceType.SUPER_SEEDER


@router.get("/reply/{reply_key}.wav")
def get_reply_audio(reply_key: str):
    """Retrieve or synthesize audio WAV for a spoken reply prompt."""
    if reply_key not in REPLIES:
        raise HTTPException(status_code=404, detail="Reply key not found")

    engine = get_voice_engine()
    text_pa = REPLIES[reply_key]["pa"]
    try:
        wav_bytes = engine.synthesize(text_pa, reply_key)
        return Response(content=wav_bytes, media_type="audio/wav")
    except VoiceServiceUnavailable:
        raise HTTPException(status_code=503, detail="Voice service unavailable") from None
