# Vaari Voice Service

Local voice processing microservice for the Vaari automated booking system.
Provides speech-to-text (ASR) via AI4Bharat IndicConformer and text-to-speech (TTS) via AI4Bharat IndicF5.

---

## 1. Architecture

The voice subsystem is split into two layers:
1. **Vaari Main Application (`http://127.0.0.1:8000`)**:
   - Manages farmer conversation state, session timeouts (30 min), rule-based field understanding, slot booking, and frontend UI (`/voice`).
   - Communicates with the voice service solely through the `VoiceEngine` interface in `app/voice/engine.py`.
   - In CI and automated test suites, `MockVoiceEngine` is used by default—models are **never** loaded during tests.
2. **Voice Microservice (`http://127.0.0.1:8100`)**:
   - Isolated in `voice_service/` with its own virtual environment (`voice_service/.venv`) and pinned dependencies (`voice_service/requirements-voice.txt`).
   - Serves endpoints: `POST /stt`, `POST /tts`, `GET /health`.

---

## 2. System Requirements

- **Operating System:** Windows, Linux, or macOS.
- **Python:** 3.10 or 3.11 for `voice_service/.venv`.
- **Memory (RAM):** 6 GB minimum (both models loaded into memory require ~5.8 GB).
- **GPU (Optional):** NVIDIA GPU with 6+ GB VRAM for live CUDA synthesis. On CPU, pre-cached prompt audio (`python tasks.py voice-cache`) is served with 0ms latency.

---

## 3. Setup Instructions

1. **Create the dedicated virtual environment:**
   ```bash
   python -m venv voice_service/.venv
   ```

2. **Install voice service requirements:**
   ```bash
   .\voice_service\.venv\Scripts\pip install -r voice_service/requirements-voice.txt
   ```

3. **Login to Hugging Face:**
   Both `ai4bharat/indic-conformer-600m-multilingual` and `ai4bharat/IndicF5` are gated models.
   Accept terms on Hugging Face and log in:
   ```bash
   hf auth login
   ```

4. **Generate synthetic or record reference voice prompt:**
   Place a ~5-10s clear Punjabi reference audio and transcript in:
   - `voice_service/reference/reference.wav` (16 kHz mono WAV)
   - `voice_service/reference/transcript.txt`

5. **Start the voice service:**
   ```bash
   python tasks.py voice-serve
   ```
   The service will listen on `http://127.0.0.1:8100`.

---

## 4. Verification with curl

### Health check
```bash
curl http://127.0.0.1:8100/health
```
Response:
```json
{"stt": "ok", "tts": "ok", "device": "cpu"}
```

### Speech-to-Text (STT)
Send a 16 kHz mono PCM WAV file (under 15s and 2 MB):
```bash
curl -X POST "http://127.0.0.1:8100/stt" -F "file=@examples/sample.wav"
```
Response:
```json
{"text": "ਸਤਿ ਸ਼੍ਰੀ ਅਕਾਲ", "seconds": 0.95}
```

### Text-to-Speech (TTS)
Request synthesis or pre-cached prompt audio:
```bash
curl -X POST "http://127.0.0.1:8100/tts" \
     -H "Content-Type: application/json" \
     -d "{\"text\": \"ਸਤਿ ਸ਼੍ਰੀ ਅਕਾਲ ਜੀ\", \"reply_key\": \"greeting\"}" \
     --output reply.wav
```

---

## 5. Privacy & Zero-Retention Rules

- **Zero Audio Retention:** Uploaded audio is read from memory streams only. Tensors and audio buffers are deleted immediately after transcription completes. No incoming audio is written to disk.
- **Zero Transcript Logging:** Log output records only HTTP request method, path, status code, and latency. Audio bytes, input text, and transcript strings are strictly forbidden from log output (conforming to `app/logging_setup.py`).
- **Session Expiry:** Farmer session draft state in Vaari expires automatically after 30 minutes of inactivity.
