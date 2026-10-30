"""VoiceEngine interface and implementations (Step V6).

Provides an abstract interface for transcribing farmer speech and synthesizing
Punjabi replies, with two implementations:
  1. MockVoiceEngine: Default for CI and all unit/integration tests. Zero models loaded.
  2. LocalVoiceEngine: Communicates with http://127.0.0.1:8100 microservice.
  3. OffVoiceEngine: Used when VAARI_VOICE=off.
"""

import json
import struct
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Optional, Tuple

from app.config import settings


class VoiceServiceUnavailable(Exception):
    """Raised when the local voice service is unreachable, times out, or fails."""
    pass


def make_dummy_wav(duration_s: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Generate a minimal valid 16-bit mono PCM WAV buffer for mock synthesis."""
    num_samples = int(duration_s * sample_rate)
    data_size = num_samples * 2
    header = bytearray(b"RIFF")
    header.extend(struct.pack("<I", 36 + data_size))
    header.extend(b"WAVEfmt ")
    header.extend(struct.pack("<I", 16))  # Subchunk1Size
    header.extend(struct.pack("<H", 1))   # AudioFormat (PCM)
    header.extend(struct.pack("<H", 1))   # NumChannels (mono)
    header.extend(struct.pack("<I", sample_rate))
    header.extend(struct.pack("<I", sample_rate * 2))  # ByteRate
    header.extend(struct.pack("<H", 2))   # BlockAlign
    header.extend(struct.pack("<H", 16))  # BitsPerSample
    header.extend(b"data")
    header.extend(struct.pack("<I", data_size))
    # 0.5s of silence
    pcm = b"\x00" * data_size
    return bytes(header + pcm)


class VoiceEngine(ABC):
    @abstractmethod
    def transcribe(self, wav_bytes: bytes) -> Tuple[str, float]:
        """Transcribe 16 kHz mono WAV bytes. Returns (text, processing_seconds)."""
        pass

    @abstractmethod
    def synthesize(self, text: str, reply_key: str) -> bytes:
        """Synthesize Punjabi text or retrieve cached prompt WAV bytes."""
        pass

    @abstractmethod
    def health(self) -> str:
        """Return engine health status: 'mock' | 'local' | 'down' | 'off'."""
        pass


class MockVoiceEngine(VoiceEngine):
    """Mock engine used by all default test suites and CI.

    Can be configured via test hooks or canned phrases.
    """
    _test_transcript: Optional[str] = None

    @classmethod
    def set_test_transcript(cls, text: Optional[str]) -> None:
        cls._test_transcript = text

    def transcribe(self, wav_bytes: bytes) -> Tuple[str, float]:
        if self._test_transcript is not None:
            return self._test_transcript, 0.05
        # Return default fallback multi-field booking transcript
        return "ਮੇਰਾ ਨੰਬਰ 9876543210 ਪਿੰਡ ਰਾਮਪੁਰ ਢਾਈ ਏਕੜ ਸੁਪਰ ਸੀਡਰ ਕੱਲ੍ਹ ਨੂੰ", 0.05

    def synthesize(self, text: str, reply_key: str) -> bytes:
        return make_dummy_wav()

    def health(self) -> str:
        return "mock"


class LocalVoiceEngine(VoiceEngine):
    """Engine that calls the dedicated voice microservice at http://127.0.0.1:8100."""

    def __init__(self, base_url: Optional[str] = None, timeout_s: Optional[float] = None):
        self.base_url = (base_url or settings.voice_service_url).rstrip("/")
        self.timeout_s = timeout_s or settings.voice_timeout_s

    def transcribe(self, wav_bytes: bytes) -> Tuple[str, float]:
        url = f"{self.base_url}/stt"
        boundary = "----WebKitFormBoundaryVaariVoice7MA4YWxkTrZu0gW"

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
            f"Content-Type: audio/wav\r\n\r\n"
        ).encode("utf-8") + wav_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                if resp.status != 200:
                    raise VoiceServiceUnavailable(f"Voice service returned status {resp.status}")
                payload = json.loads(resp.read().decode("utf-8"))
                return payload.get("text", ""), float(payload.get("seconds", 0.0))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise VoiceServiceUnavailable(f"Cannot reach voice service: {e}") from e

    def synthesize(self, text: str, reply_key: str) -> bytes:
        url = f"{self.base_url}/tts"
        payload_bytes = json.dumps({"text": text, "reply_key": reply_key}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                if resp.status != 200:
                    raise VoiceServiceUnavailable(f"TTS service returned status {resp.status}")
                return resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise VoiceServiceUnavailable(f"Cannot reach TTS service: {e}") from e

    def health(self) -> str:
        url = f"{self.base_url}/health"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("stt") == "ok":
                        return "local"
        except Exception:
            pass
        return "down"


class OffVoiceEngine(VoiceEngine):
    def transcribe(self, wav_bytes: bytes) -> Tuple[str, float]:
        raise VoiceServiceUnavailable("Voice booking is switched off")

    def synthesize(self, text: str, reply_key: str) -> bytes:
        raise VoiceServiceUnavailable("Voice booking is switched off")

    def health(self) -> str:
        return "off"


_current_engine: Optional[VoiceEngine] = None


def get_voice_engine() -> VoiceEngine:
    global _current_engine
    if _current_engine is not None:
        return _current_engine

    mode = settings.voice
    if mode == "off" or not settings.voice_booking:
        return OffVoiceEngine()
    elif mode == "local":
        return LocalVoiceEngine()
    else:
        return MockVoiceEngine()


def set_voice_engine(engine: Optional[VoiceEngine]) -> None:
    """Override engine instance for testing."""
    global _current_engine
    _current_engine = engine
