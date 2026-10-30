"""Benchmark script for Vaari Voice Spike (Step V1).

Measures:
  - Model load time (IndicConformer ASR & IndicF5 TTS)
  - Memory usage (RAM and GPU VRAM if available)
  - Seconds per clip for speech-to-text (STT)
  - Seconds per sentence for speech synthesis (TTS)
  - Whether GPU was used
  - Generates docs/VOICE_BENCH.md and advises LIVE vs CACHED mode
"""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def get_memory_mb():
    try:
        import psutil

        process = psutil.Process(os.getpid())
        ram_mb = process.memory_info().rss / (1024 * 1024)
    except Exception:
        ram_mb = 0.0

    gpu_mb = 0.0
    try:
        import torch

        if torch.cuda.is_available():
            gpu_mb = torch.cuda.memory_allocated() / (1024 * 1024)
    except Exception:
        pass

    return ram_mb, gpu_mb


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    print("=" * 70)
    print("  Vaari Voice Spike: Model Benchmarking (Step V1)")
    print("=" * 70)

    try:
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
    except ImportError:
        device = "cpu"
        device_name = "CPU (torch not loaded)"

    print(f"Device: {device} ({device_name})")

    # 1. Benchmark STT (IndicConformer)
    print("\n--- 1. IndicConformer (ASR) Benchmark ---")
    stt_load_time = 0.0
    stt_results = []

    t0 = time.perf_counter()
    stt_model = None
    try:
        import torchaudio
        from transformers import AutoModel

        stt_model = AutoModel.from_pretrained(
            "ai4bharat/indic-conformer-600m-multilingual",
            trust_remote_code=True,
        )
        if device == "cuda":
            stt_model = stt_model.to("cuda")
        stt_load_time = time.perf_counter() - t0
        print(f"IndicConformer loaded in {stt_load_time:.2f}s")
    except Exception as e:
        print(f"Could not load IndicConformer: {e}")

    test_clips_dir = ROOT / "voice_service" / "test_clips"
    clips = ["clip1.wav", "clip2.wav", "clip3.wav"]

    for clip_name in clips:
        clip_path = test_clips_dir / clip_name
        if not clip_path.exists():
            print(f"Clip {clip_name} not found, skipping...")
            continue

        if stt_model is not None:
            t_start = time.perf_counter()
            try:
                import soundfile as sf

                data, sr = sf.read(str(clip_path))
                if data.ndim > 1:
                    data = data.mean(axis=1)
                wav = torch.tensor(data, dtype=torch.float32).unsqueeze(0)
                if sr != 16000:
                    import torchaudio

                    resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)
                    wav = resampler(wav)
                if device == "cuda":
                    wav = wav.to("cuda")

                transcription = stt_model(wav, "pa", "ctc")
                duration = time.perf_counter() - t_start
                stt_results.append((clip_name, duration, str(transcription)))
                print(f"  [{clip_name}] {duration:.2f}s -> {transcription}")
            except Exception as e:
                print(f"  [{clip_name}] Inference error: {e}")
                stt_results.append((clip_name, 0.0, f"Error: {e}"))
        else:
            stt_results.append((clip_name, 0.0, "Model not loaded"))

    # 2. Benchmark TTS (IndicF5)
    print("\n--- 2. IndicF5 (TTS) Benchmark ---")
    tts_load_time = 0.0
    tts_results = []

    ref_wav = ROOT / "voice_service" / "reference" / "reference.wav"
    ref_txt = ROOT / "voice_service" / "reference" / "transcript.txt"
    ref_prompt = (
        ref_txt.read_text(encoding="utf-8").strip()
        if ref_txt.exists()
        else "ਸਤਿ ਸ਼੍ਰੀ ਅਕਾਲ ਜੀ, ਵਾਰੀ ਆਟੋਮੇਟਿਡ ਬੁਕਿੰਗ ਸਿਸਟਮ ਵਿੱਚ ਤੁਹਾਡਾ ਸੁਆਗਤ ਹੈ।"
    )

    t0 = time.perf_counter()
    tts_model = None
    vocoder = None
    try:
        from f5_tts.infer.utils_infer import load_vocoder
        from f5_tts.model import CFM, DiT
        from f5_tts.model.utils import get_tokenizer
        from huggingface_hub import hf_hub_download
        from safetensors import safe_open

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
        tts_model = CFM(
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
        tts_model.load_state_dict(ema_sd, strict=False)
        tts_model = tts_model.to(device)

        vocoder = load_vocoder(vocoder_name="vocos", is_local=False, device=device)
        tts_load_time = time.perf_counter() - t0
        print(f"IndicF5 loaded in {tts_load_time:.2f}s")
    except Exception as e:
        print(f"Could not load IndicF5: {e}")

    sentences = [
        "ਸਤਿ ਸ਼੍ਰੀ ਅਕਾਲ ਜੀ, ਵਾਰੀ ਆਟੋਮੇਟਿਡ ਸਿਸਟਮ ਵਿੱਚ ਤੁਹਾਡਾ ਸੁਆਗਤ ਹੈ।",
        "ਕਿਰਪਾ ਕਰਕੇ ਆਪਣਾ ਫ਼ੋਨ ਨੰਬਰ ਅਤੇ ਪਿੰਡ ਦਾ ਨਾਮ ਦੱਸੋ ਜੀ।",
        "ਤੁਹਾਡੀ ਸੁਪਰ ਸੀਡਰ ਦੀ ਬੁਕਿੰਗ ਪੰਜ ਨਵੰਬਰ ਲਈ ਪੱਕੀ ਕਰ ਲਈ ਗਈ ਹੈ।",
    ]

    out_dir = ROOT / "voice_service" / "bench_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, s in enumerate(sentences, 1):
        if tts_model is not None and vocoder is not None and ref_wav.exists():
            t_start = time.perf_counter()
            try:
                import numpy as np
                import soundfile as sf
                from f5_tts.infer.utils_infer import infer_batch_process

                data, sr = sf.read(str(ref_wav))
                if data.ndim > 1:
                    data = data.mean(axis=1)
                audio_tensor = torch.tensor(data, dtype=torch.float32).unsqueeze(0)

                # Use nfe_step=4 for benchmark test on CPU to measure step rate
                final_wave, final_sr, _ = next(
                    infer_batch_process(
                        (audio_tensor, sr),
                        ref_prompt,
                        [s],
                        tts_model,
                        vocoder,
                        mel_spec_type="vocos",
                        nfe_step=4,
                        device=device,
                    )
                )
                duration = time.perf_counter() - t_start
                # Scale up to 32 steps to reflect full quality synthesis time
                est_full_duration = duration * 8.0
                out_path = out_dir / f"sentence_{i}.wav"
                sf.write(str(out_path), np.array(final_wave, dtype=np.float32), samplerate=final_sr)
                tts_results.append((f"Sentence {i} (measured 4 steps, est 32 steps)", est_full_duration, s))
                print(f"  [Sentence {i}] {duration:.2f}s (4 steps) -> ~{est_full_duration:.2f}s (32 steps)")
            except Exception as e:
                print(f"  [Sentence {i}] Inference error: {e}")
                tts_results.append((f"Sentence {i}", 0.0, f"Error: {e}"))
        else:
            tts_results.append((f"Sentence {i}", 0.0, "Model or reference not available"))

    ram_mb, gpu_mb = get_memory_mb()
    print(f"\nMemory used: RAM ~{ram_mb:.0f} MB | VRAM ~{gpu_mb:.0f} MB")

    # Determine reply mode
    valid_tts_times = [d for _, d, _ in tts_results if d > 0]
    avg_tts = sum(valid_tts_times) / len(valid_tts_times) if valid_tts_times else 999.0
    mode = "LIVE" if (avg_tts < 5.0 and len(valid_tts_times) > 0) else "CACHED"

    print("\n" + "=" * 70)
    print(f"  Decision: {mode} replies")
    if mode == "LIVE":
        print(f"  Average sentence synthesis time: {avg_tts:.2f}s (< 5.0s threshold)")
    else:
        print(f"  Average sentence synthesis time: {avg_tts:.2f}s (>= 5.0s threshold or cached mode needed)")
    print("=" * 70)

    # Write docs/VOICE_BENCH.md
    bench_md = ROOT / "docs" / "VOICE_BENCH.md"
    content = f"""# Voice Model Benchmark (Step V1)

- **Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}
- **Device:** {device.upper()} ({device_name})
- **STT Model:** `ai4bharat/indic-conformer-600m-multilingual`
- **TTS Model:** `ai4bharat/IndicF5`

## 1. Load Times & Memory
- **STT Load Time:** {stt_load_time:.2f} s
- **TTS Load Time:** {tts_load_time:.2f} s
- **Process Memory (RAM):** {ram_mb:.0f} MB
- **GPU Memory Allocated:** {gpu_mb:.0f} MB

## 2. Speech-to-Text (IndicConformer, CTC, language='pa')
| Clip | Duration (s) | Transcript |
| --- | --- | --- |
"""
    for name, dur, tr in stt_results:
        content += f"| {name} | {dur:.2f} | {tr} |\n"

    content += """
## 3. Text-to-Speech (IndicF5)
| Item | Duration (s) | Text |
| --- | --- | --- |
"""
    for name, dur, text in tts_results:
        content += f"| {name} | {dur:.2f} | {text} |\n"

    content += f"""
## 4. Decision & Reply Mode
- **Average TTS Latency:** {avg_tts:.2f} s per sentence
- **Decision:** **{mode}** replies (Threshold: < 5.0 s for LIVE replies; otherwise CACHED)
"""
    bench_md.write_text(content, encoding="utf-8")
    print(f"\nWrote benchmark results to {bench_md.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
