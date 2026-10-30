"""Unit tests for the voice microservice endpoints (Step V2).

Tests run using TestClient without downloading or requiring real weights.
"""

import io
from unittest.mock import MagicMock, patch

import pytest

try:
    import numpy as np
    import soundfile as sf
    import torch
    from fastapi.testclient import TestClient

    from voice_service.server import app

    HAS_VOICE_DEPS = True
except ImportError:
    HAS_VOICE_DEPS = False
    app = None
    np = None
    sf = None
    torch = None

pytestmark = pytest.mark.skipif(
    not HAS_VOICE_DEPS,
    reason="voice_service dependencies (torch, soundfile) not installed in main environment",
)


@pytest.fixture
def client():
    if not HAS_VOICE_DEPS or app is None:
        pytest.skip("voice_service dependencies not installed")
    # Bypass startup lifespan loading of heavy models during testing
    with patch("voice_service.server.load_stt"), patch("voice_service.server.load_tts"):
        with TestClient(app) as test_client:
            yield test_client


def test_health_when_models_down(client):
    with patch("voice_service.server.stt_model", None), patch("voice_service.server.tts_model", None):
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["stt"] == "down"
        assert data["tts"] == "down"
        assert "device" in data


def test_health_when_models_ok(client):
    with patch("voice_service.server.stt_model", MagicMock()), patch("voice_service.server.tts_model", MagicMock()):
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["stt"] == "ok"
        assert data["tts"] == "ok"


def test_stt_empty_file_rejected(client):
    with patch("voice_service.server.stt_model", MagicMock()):
        files = {"file": ("test.wav", b"", "audio/wav")}
        res = client.post("/stt", files=files)
        assert res.status_code == 400


def test_stt_oversized_file_rejected(client):
    with patch("voice_service.server.stt_model", MagicMock()):
        oversized = b"0" * (2 * 1024 * 1024 + 10)
        files = {"file": ("test.wav", oversized, "audio/wav")}
        res = client.post("/stt", files=files)
        assert res.status_code == 413


def test_stt_successful_mock_inference(client):
    # Create 1 second 16kHz sine wave
    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    sine = 0.5 * np.sin(2 * np.pi * 440 * t)
    buf = io.BytesIO()
    sf.write(buf, sine, sr, format="WAV")
    wav_bytes = buf.getvalue()

    mock_model = MagicMock(return_value="ਸਤਿ ਸ਼੍ਰੀ ਅਕਾਲ")
    with patch("voice_service.server.stt_model", mock_model):
        files = {"file": ("test.wav", wav_bytes, "audio/wav")}
        res = client.post("/stt", files=files)
        assert res.status_code == 200
        data = res.json()
        assert data["text"] == "ਸਤਿ ਸ਼੍ਰੀ ਅਕਾਲ"
        assert "seconds" in data
        assert data["seconds"] >= 0.0


def test_tts_returns_cached_file_if_available(client, tmp_path):
    cached_file = tmp_path / "greeting.wav"
    cached_file.write_bytes(b"RIFFdummywavbytes")
    with patch("voice_service.server.CACHE_DIR", tmp_path):
        res = client.post("/tts", json={"text": "hello", "reply_key": "greeting"})
        assert res.status_code == 200
        assert res.headers["content-type"] == "audio/wav"
        assert res.content == b"RIFFdummywavbytes"


def test_tts_service_unavailable_when_model_missing(client, tmp_path):
    with patch("voice_service.server.CACHE_DIR", tmp_path), \
         patch("voice_service.server.tts_model", None):
        res = client.post("/tts", json={"text": "hello", "reply_key": "nonexistent"})
        assert res.status_code == 503
