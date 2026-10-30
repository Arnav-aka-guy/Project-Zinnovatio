"""API tests for voice booking routes (Step V6).

Uses MockVoiceEngine (no heavy models downloaded or loaded).
Tests:
  - Happy path full conversation flow
  - Spoken confirmation vs button tap confirmation
  - Cancellation flow
  - 1-field retry and correction
  - 2-strikes fallback (saving needs_info if phone present, saving nothing if phone absent)
  - Audio validation limits (empty, > 2MB, > 15 seconds)
  - Prompt audio endpoint
  - Health endpoint voice field
"""

import struct

from fastapi.testclient import TestClient

from app.enums import RequestSource, RequestStatus
from app.models import Request
from app.voice.engine import MockVoiceEngine, make_dummy_wav, set_voice_engine


def make_test_wav(duration_s: float = 1.0, sample_rate: int = 16000) -> bytes:
    return make_dummy_wav(duration_s=duration_s, sample_rate=sample_rate)


def test_voice_health(client: TestClient):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert "voice" in data
    assert data["voice"] in ("mock", "local", "down", "off")


def test_voice_prompt_audio_endpoint(client: TestClient):
    res = client.get("/api/voice/reply/greeting.wav")
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/wav"
    assert len(res.content) > 44

    # Unknown reply key -> 404
    res_bad = client.get("/api/voice/reply/unknown_key_xyz.wav")
    assert res_bad.status_code == 404


def test_voice_booking_happy_path(client: TestClient, temp_db):
    engine = MockVoiceEngine()
    set_voice_engine(engine)

    # 1. Start Session
    res = client.post("/api/voice/session")
    assert res.status_code == 200
    sess = res.json()
    sid = sess["session_id"]
    assert sess["state"] == "idle"
    assert sess["prompt"]["key"] == "greeting"

    # 2. Consent
    res = client.post("/api/voice/consent", json={"session_id": sid})
    assert res.status_code == 200
    sess = res.json()
    assert sess["state"] == "consented"
    assert sess["current_field"] == "phone"
    assert sess["prompt"]["key"] == "ask_phone"

    # 3. Turn: Provide Phone
    engine.set_test_transcript("ਮੇਰਾ ਨੰਬਰ 9876543210 ਹੈ")
    wav = make_test_wav()
    res = client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", wav, "audio/wav")},
    )
    assert res.status_code == 200
    sess = res.json()
    assert sess["collected_fields"]["phone"] == "9876543210"
    assert sess["current_field"] == "village"
    assert sess["prompt"]["key"] == "ask_village"

    # 4. Turn: Provide Village
    engine.set_test_transcript("ਪਿੰਡ ਰਾਮਪੁਰ")
    res = client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", wav, "audio/wav")},
    )
    assert res.status_code == 200
    sess = res.json()
    assert sess["collected_fields"]["village"] == "Rampur"
    assert sess["current_field"] == "acres"
    assert sess["prompt"]["key"] == "ask_acres"

    # 5. Turn: Provide Acres
    engine.set_test_transcript("ਢਾਈ ਏਕੜ ਜ਼ਮੀਨ ਹੈ")
    res = client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", wav, "audio/wav")},
    )
    assert res.status_code == 200
    sess = res.json()
    assert sess["collected_fields"]["acres"] == 2.5
    assert sess["current_field"] == "machine"
    assert sess["prompt"]["key"] == "ask_machine"

    # 6. Turn: Provide Machine
    engine.set_test_transcript("ਸੁਪਰ ਸੀਡਰ ਚਾਹੀਦਾ ਹੈ")
    res = client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", wav, "audio/wav")},
    )
    assert res.status_code == 200
    sess = res.json()
    assert sess["collected_fields"]["machine"] == "Super Seeder"
    assert sess["current_field"] == "harvest_date"
    assert sess["prompt"]["key"] == "ask_harvest_date"

    # 7. Turn: Provide Date -> Advances to confirming!
    engine.set_test_transcript("ਕੱਲ੍ਹ ਨੂੰ ਲੈ ਆਓ")
    res = client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", wav, "audio/wav")},
    )
    assert res.status_code == 200
    sess = res.json()
    assert sess["state"] == "confirming"
    assert sess["current_field"] == "confirm"
    assert sess["prompt"]["key"] == "ask_confirm"

    # 8. Confirm via Button tap: Yes
    res = client.post("/api/voice/answer", json={"session_id": sid, "answer": "yes"})
    assert res.status_code == 200
    sess = res.json()
    assert sess["state"] == "confirmed"
    assert sess["request_id"] is not None

    # Verify request in database
    with temp_db() as s:
        req_row = s.query(Request).filter_by(id=int(sess["request_id"])).first()
        assert req_row is not None
        assert req_row.source == RequestSource.VOICE
        assert req_row.acres_x100 == 250


def test_voice_spoken_confirmation(client: TestClient, temp_db):
    engine = MockVoiceEngine()
    set_voice_engine(engine)

    res = client.post("/api/voice/session")
    sid = res.json()["session_id"]
    client.post("/api/voice/consent", json={"session_id": sid})

    # Supply all fields in one multi-field turn
    engine.set_test_transcript("ਨੰਬਰ 9876543210 ਪਿੰਡ ਰਾਮਪੁਰ ਢਾਈ ਏਕੜ ਸੁਪਰ ਸੀਡਰ ਕੱਲ੍ਹ ਨੂੰ")
    wav = make_test_wav()
    res = client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", wav, "audio/wav")},
    )
    assert res.json()["state"] == "confirming"

    # Spoken confirmation "ਹਾਂਜੀ"
    engine.set_test_transcript("ਹਾਂਜੀ ਬਿਲਕੁਲ ਸਹੀ ਹੈ")
    res_conf = client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", wav, "audio/wav")},
    )
    assert res_conf.status_code == 200
    sess = res_conf.json()
    assert sess["state"] == "confirmed"
    assert sess["request_id"] is not None

    with temp_db() as s:
        req_row = s.query(Request).filter_by(id=int(sess["request_id"])).first()
        assert req_row is not None
        assert req_row.source == RequestSource.VOICE


def test_voice_cancellation_flow(client: TestClient):
    engine = MockVoiceEngine()
    set_voice_engine(engine)

    res = client.post("/api/voice/session")
    sid = res.json()["session_id"]
    client.post("/api/voice/consent", json={"session_id": sid})

    # Put in confirming state
    engine.set_test_transcript("ਨੰਬਰ 9876543210 ਪਿੰਡ ਰਾਮਪੁਰ ਢਾਈ ਏਕੜ ਸੁਪਰ ਸੀਡਰ ਕੱਲ੍ਹ")
    wav = make_test_wav()
    client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", wav, "audio/wav")},
    )

    # Cancel via answer: no
    res = client.post("/api/voice/answer", json={"session_id": sid, "answer": "no"})
    assert res.status_code == 200
    sess = res.json()
    assert sess["state"] == "cancelled"
    assert sess["prompt"]["key"] == "cancelled"


def test_voice_retry_correction(client: TestClient):
    engine = MockVoiceEngine()
    set_voice_engine(engine)

    res = client.post("/api/voice/session")
    sid = res.json()["session_id"]
    client.post("/api/voice/consent", json={"session_id": sid})

    wav = make_test_wav()

    # 1. Unclear speech on phone
    engine.set_test_transcript("ਕੁਝ ਸਮਝ ਨਹੀਂ ਆਇਆ ਸ਼ੋਰ ਸੀ")
    res1 = client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", wav, "audio/wav")},
    )
    assert res1.json()["prompt"]["key"] == "did_not_understand"
    assert res1.json()["current_field"] == "phone"

    # 2. Correct phone on retry
    engine.set_test_transcript("9876543210")
    res2 = client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", wav, "audio/wav")},
    )
    assert res2.json()["collected_fields"]["phone"] == "9876543210"
    assert res2.json()["current_field"] == "village"


def test_two_strikes_fallback_with_phone(client: TestClient, temp_db):
    engine = MockVoiceEngine()
    set_voice_engine(engine)

    res = client.post("/api/voice/session")
    sid = res.json()["session_id"]
    client.post("/api/voice/consent", json={"session_id": sid})

    wav = make_test_wav()

    # Collect phone
    engine.set_test_transcript("9876543210")
    client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", wav, "audio/wav")},
    )

    # Now on village: 1st fail
    engine.set_test_transcript("ਅਜੀਬ ਜਿਹਾ ਸ਼ਬਦ")
    res_fail1 = client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", wav, "audio/wav")},
    )
    assert res_fail1.json()["prompt"]["key"] == "did_not_understand"

    # 2nd fail on village -> triggers 2-strikes rule!
    res_fail2 = client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", wav, "audio/wav")},
    )
    sess = res_fail2.json()
    assert sess["state"] == "needs_info"
    assert sess["prompt"]["key"] == "will_call_you"
    assert sess["request_id"] is not None

    with temp_db() as s:
        req_row = s.query(Request).filter_by(id=int(sess["request_id"])).first()
        assert req_row.status == RequestStatus.NEEDS_INFO
        assert req_row.source == RequestSource.VOICE


def test_two_strikes_fallback_without_phone(client: TestClient, temp_db):
    engine = MockVoiceEngine()
    set_voice_engine(engine)

    res = client.post("/api/voice/session")
    sid = res.json()["session_id"]
    client.post("/api/voice/consent", json={"session_id": sid})

    wav = make_test_wav()

    # Fail twice on phone
    engine.set_test_transcript("ਅਣਪਛਾਤੀ ਆਵਾਜ਼")
    client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", wav, "audio/wav")},
    )
    res_fail2 = client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", wav, "audio/wav")},
    )
    sess = res_fail2.json()
    assert sess["state"] == "cancelled"
    assert sess["prompt"]["key"] == "will_call_you"
    assert sess["request_id"] is None

    with temp_db() as s:
        assert s.query(Request).count() == 0


def test_audio_validation_limits(client: TestClient):
    res = client.post("/api/voice/session")
    sid = res.json()["session_id"]

    # Empty audio -> 400
    res_empty = client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", b"", "audio/wav")},
    )
    assert res_empty.status_code == 400

    # Oversized audio (> 2 MB) -> 413
    oversized = b"RIFF" + b"\x00" * (2 * 1024 * 1024 + 100)
    res_big = client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", oversized, "audio/wav")},
    )
    assert res_big.status_code == 413

    # Exceeding 15-second cap -> 400
    # 16-bit 16kHz mono = 32000 bytes/sec. 16 seconds = 512000 bytes
    long_data = b"\x00" * 512000
    long_wav = (
        b"RIFF"
        + struct.pack("<I", 36 + len(long_data))
        + b"WAVEfmt "
        + struct.pack("<I", 16)
        + struct.pack("<H", 1)
        + struct.pack("<H", 1)
        + struct.pack("<I", 16000)
        + struct.pack("<I", 32000)
        + struct.pack("<H", 2)
        + struct.pack("<H", 16)
        + b"data"
        + struct.pack("<I", len(long_data))
        + long_data
    )
    res_long = client.post(
        "/api/voice/turn",
        data={"session_id": sid},
        files={"audio": ("rec.wav", long_wav, "audio/wav")},
    )
    assert res_long.status_code == 400
