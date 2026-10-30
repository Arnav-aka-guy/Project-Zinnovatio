"""Pre-generate fixed Punjabi spoken replies with IndicF5 into voice_service/cache/ (Step V3).

Usage:
  python tasks.py voice-cache [--force]
"""

import argparse
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "voice_service" / "cache"

# Ensure app is importable
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.voice.replies import REPLIES  # noqa: E402


def make_fallback_wav(path: Path, text: str):
    """Generate a placeholder synthetic sine wav if model generation is unavailable."""
    import numpy as np
    import soundfile as sf

    sr = 24000
    duration = min(4.0, max(1.5, len(text) * 0.05))
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # Gentle two-tone chime
    wave = 0.25 * np.sin(2 * np.pi * 523.25 * t) + 0.15 * np.sin(2 * np.pi * 659.25 * t)
    # Fade in/out
    fade = int(sr * 0.05)
    wave[:fade] *= np.linspace(0, 1, fade)
    wave[-fade:] *= np.linspace(1, 0, fade)
    sf.write(str(path), wave.astype(np.float32), sr)


def main():
    parser = argparse.ArgumentParser(description="Pre-generate voice replies for Vaari")
    parser.add_argument("--force", action="store_true", help="Overwrite existing cached files")
    parser.add_argument("--steps", type=int, default=4, help="Diffusion steps (default 4 on CPU)")
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Target cache directory: {CACHE_DIR.relative_to(ROOT)}")
    print(f"Total replies to cache: {len(REPLIES)}")

    # Try loading IndicF5
    tts_model = None
    vocoder = None
    device = "cpu"
    ref_audio_tensor = None
    ref_audio_sr = 16000
    ref_prompt_text = "ਸਤਿ ਸ਼੍ਰੀ ਅਕਾਲ ਜੀ, ਵਾਰੀ ਆਟੋਮੇਟਿਡ ਬੁਕਿੰਗ ਸਿਸਟਮ ਵਿੱਚ ਤੁਹਾਡਾ ਸੁਆਗਤ ਹੈ।"

    try:
        import soundfile as sf
        import torch
        from f5_tts.infer.utils_infer import load_vocoder
        from f5_tts.model import CFM, DiT
        from f5_tts.model.utils import get_tokenizer
        from huggingface_hub import hf_hub_download
        from safetensors import safe_open

        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading IndicF5 TTS model on {device}...")

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

        print("IndicF5 loaded successfully.")
    except Exception as e:
        print(f"Warning: Could not load IndicF5 ({e}). Falling back to synthetic voice generator.")
        tts_model = None

    infer_batch_process = None
    if tts_model is not None:
        from f5_tts.infer.utils_infer import infer_batch_process
    import numpy as np
    import soundfile as sf

    for key, item in REPLIES.items():
        out_wav = CACHE_DIR / f"{key}.wav"
        if out_wav.exists() and not args.force:
            print(f"  [cache hit] {key}.wav already exists, skipping")
            continue

        text_pa = item["pa"]
        t0 = time.perf_counter()

        if tts_model is not None and vocoder is not None and ref_audio_tensor is not None:
            try:
                print(f"  Generating {key}.wav with IndicF5 ({args.steps} steps)...")
                final_wave, final_sr, _ = next(
                    infer_batch_process(
                        (ref_audio_tensor, ref_audio_sr),
                        ref_prompt_text,
                        [text_pa],
                        tts_model,
                        vocoder,
                        mel_spec_type="vocos",
                        nfe_step=args.steps,
                        device=device,
                    )
                )
                sf.write(str(out_wav), np.array(final_wave, dtype=np.float32), samplerate=final_sr)
                elapsed = time.perf_counter() - t0
                print(f"  [saved] {key}.wav in {elapsed:.2f}s")
                continue
            except Exception as e:
                print(f"  IndicF5 generation failed for {key}: {e}. Using synthetic fallback.")

        # Fallback
        make_fallback_wav(out_wav, text_pa)
        elapsed = time.perf_counter() - t0
        print(f"  [saved fallback] {key}.wav in {elapsed:.2f}s")

    print(f"\nAll {len(REPLIES)} replies cached in {CACHE_DIR.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
