"""Vaari Voice Service (Step V2).

Local microservice running on 127.0.0.1:8100.
Provides:
  - POST /stt : Speech-to-Text using AI4Bharat IndicConformer (language 'pa', CTC)
  - POST /tts : Text-to-Speech using AI4Bharat IndicF5 / pre-cached audio
  - GET /health : Service status and device information

Privacy & Security:
  - Uploaded audio is processed purely in memory and immediately discarded.
  - No audio or transcript is written to disk or recorded in logs.
  - Logging is restricted to method, path, status, and latency.
"""

import io
import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import soundfile as sf
import torch
from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(__file__).resolve().parent / "cache"

# Configure privacy-safe logging (no text or audio content)
logger = logging.getLogger("voice_service")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(asctime)s] [voice_service] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# Globals for models
device = "cuda" if torch.cuda.is_available() else "cpu"
stt_model = None
tts_model = None
vocoder = None
ref_audio_tensor = None
ref_audio_sr = 16000
ref_prompt_text = ""


def load_stt():
    global stt_model
    try:
        from transformers import AutoModel

        logger.info("Loading IndicConformer STT model...")
        model = AutoModel.from_pretrained(
            "ai4bharat/indic-conformer-600m-multilingual",
            trust_remote_code=True,
        )
        if device == "cuda":
            model = model.to("cuda")
        stt_model = model
        logger.info("IndicConformer loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load IndicConformer: {e.__class__.__name__}")
        stt_model = None


def load_tts():
    global tts_model, vocoder, ref_audio_tensor, ref_audio_sr, ref_prompt_text
    try:
        from f5_tts.infer.utils_infer import load_vocoder
        from f5_tts.model import CFM, DiT
        from f5_tts.model.utils import get_tokenizer
        from huggingface_hub import hf_hub_download
        from safetensors import safe_open

        logger.info("Loading IndicF5 TTS model...")
        vocab_path = hf_hub_download("ai4bharat/IndicF5", "checkpoints/vocab.txt")
        ckpt_path = hf_hub_download("ai4bharat/IndicF5", "model.safetensors")

        ema_sd = {}
        with safe_open(ckpt_path, framework="pt", device=device) as f:
            for k in f.keys():
                if k.startswith("ema_model._orig_mod."):
                    clean_k = k[len("ema_model._orig_mod.") :]
                    ema_sd[clean_k] = f.get_tensor(k)

        vocab_char_map, vocab_size = get_tokenizer(vocab_path, "custom")
        dit = DiT(
            dim=1024,
            depth=22,
            heads=16,
            ff_mult=2,
            text_dim=512,
            conv_layers=4,
            text_num_embeds=vocab_size,
            mel_dim=100,
        )
        cfm = CFM(
            transformer=dit,
            mel_spec_kwargs=dict(
                target_sample_rate=24000,
                n_mel_channels=100,
                hop_length=256,
                win_length=1024,
                n_fft=1024,
                mel_spec_type="vocos",
            ),
            odeint_kwargs=dict(method="euler"),
            vocab_char_map=vocab_char_map,
        )
        cfm.load_state_dict(ema_sd, strict=False)
        cfm.eval()
        if device == "cuda":
            cfm = cfm.to("cuda")
        tts_model = cfm

        vocoder = load_vocoder(vocoder_name="vocos", is_local=False, device=device)

        ref_wav_path = ROOT / "voice_service" / "reference" / "reference.wav"
        ref_txt_path = ROOT / "voice_service" / "reference" / "transcript.txt"
        if ref_wav_path.exists():
            data, sr = sf.read(str(ref_wav_path))
            if data.ndim > 1:
                data = data.mean(axis=1)
            ref_audio_tensor = torch.tensor(data, dtype=torch.float32).unsqueeze(0)
            ref_audio_sr = sr
        if ref_txt_path.exists():
            ref_prompt_text = ref_txt_path.read_text(encoding="utf-8").strip()

        logger.info("IndicF5 TTS model and vocoder loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load IndicF5: {e.__class__.__name__}")
        tts_model = None
        vocoder = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load models on server startup
    load_stt()
    load_tts()
    yield


app = FastAPI(title="Vaari Voice Service", lifespan=lifespan)

# Allow requests from local Vaari instance
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def privacy_logging_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000
    # Log only method, path, status, and duration (never payloads or transcripts)
    logger.info(f"{request.method} {request.url.path} status={response.status_code} latency={duration_ms:.1f}ms")
    return response


@app.get("/health")
def health():
    return {
        "stt": "ok" if stt_model is not None else "down",
        "tts": "ok" if tts_model is not None else "down",
        "device": device,
    }


@app.post("/stt")
async def speech_to_text(file: UploadFile = File(...)):
    """Transcribe audio WAV file to Punjabi text.

    Audio is processed directly in memory and immediately discarded.
    """
    if stt_model is None:
        raise HTTPException(status_code=503, detail="STT model not loaded")

    # Read uploaded bytes (cap at 2 MB)
    file_bytes = await file.read()
    if len(file_bytes) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file exceeds 2 MB limit")
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    t0 = time.perf_counter()
    try:
        data, sr = sf.read(io.BytesIO(file_bytes))
        # Ensure mono
        if data.ndim > 1:
            data = data.mean(axis=1)

        # Check maximum duration (15 seconds)
        duration_sec = len(data) / sr
        if duration_sec > 15.0:
            raise HTTPException(status_code=400, detail="Audio exceeds 15 second maximum limit")

        wav = torch.tensor(data, dtype=torch.float32).unsqueeze(0)
        if sr != 16000:
            import torchaudio

            resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)
            wav = resampler(wav)

        if device == "cuda":
            wav = wav.to("cuda")

        with torch.inference_mode():
            raw_transcription = stt_model(wav, "pa", "ctc")
        text = str(raw_transcription).strip()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Inference error in /stt: {e.__class__.__name__}")
        raise HTTPException(status_code=500, detail="Transcription failed") from None
    finally:
        # Immediately discard audio bytes and tensors from memory
        del file_bytes
        try:
            del data
            del wav
        except NameError:
            pass

    proc_seconds = time.perf_counter() - t0
    return {"text": text, "seconds": round(proc_seconds, 3)}


class TTSRequest(BaseModel):
    text: str
    reply_key: Optional[str] = None


@app.post("/tts")
def text_to_speech(req: TTSRequest):
    """Synthesize Punjabi text to WAV audio or serve pre-cached prompt audio."""
    # 1. Check if a cached WAV exists for this reply_key
    if req.reply_key:
        safe_key = Path(req.reply_key).name
        cached_wav = CACHE_DIR / f"{safe_key}.wav"
        if cached_wav.exists():
            return Response(content=cached_wav.read_bytes(), media_type="audio/wav")

    # 2. If TTS model is available, synthesize live (or return error if unavailable)
    if tts_model is None or vocoder is None or ref_audio_tensor is None:
        raise HTTPException(status_code=503, detail="TTS model or reference prompt audio not available")

    try:
        import numpy as np
        from f5_tts.infer.utils_infer import infer_batch_process

        # Use 4 steps on CPU for responsive fallback, or 32 on CUDA
        steps = 32 if device == "cuda" else 4
        final_wave, final_sr, _ = next(
            infer_batch_process(
                (ref_audio_tensor, ref_audio_sr),
                ref_prompt_text,
                [req.text],
                tts_model,
                vocoder,
                mel_spec_type="vocos",
                nfe_step=steps,
                device=device,
            )
        )
        out_buf = io.BytesIO()
        sf.write(out_buf, np.array(final_wave, dtype=np.float32), samplerate=final_sr, format="WAV")
        wav_bytes = out_buf.getvalue()
        return Response(content=wav_bytes, media_type="audio/wav")
    except Exception as e:
        logger.error(f"Inference error in /tts: {e.__class__.__name__}")
        raise HTTPException(status_code=500, detail="Synthesis failed") from None
