"""Generate synthetic 16 kHz mono PCM WAV samples for local testing and benchmarking.

Creates:
  - voice_service/reference/reference.wav (7.5 seconds synthetic voice tone harmonics)
  - voice_service/reference/transcript.txt
  - voice_service/test_clips/clip1.wav (invented farmer booking: 4 acres super seeder)
  - voice_service/test_clips/clip2.wav (invented phone number)
  - voice_service/test_clips/clip3.wav (yes confirmation)
"""

import math
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def generate_synthetic_wav(path: Path, duration_s: float = 6.0, sample_rate: int = 16000, base_freq: float = 180.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(duration_s * sample_rate)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)

        frames = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            # Voice-like harmonic series with envelope modulation
            f0 = base_freq + 20.0 * math.sin(2.0 * math.pi * 1.5 * t)
            h1 = 0.50 * math.sin(2.0 * math.pi * f0 * t)
            h2 = 0.25 * math.sin(2.0 * math.pi * 2.0 * f0 * t)
            h3 = 0.15 * math.sin(2.0 * math.pi * 3.0 * f0 * t)
            h4 = 0.10 * math.sin(2.0 * math.pi * 4.0 * f0 * t)

            # Syllable-like rhythmic amplitude envelope (3 Hz cadence)
            cadence = 0.3 + 0.7 * max(0.0, math.sin(2.0 * math.pi * 3.2 * t))
            sample_float = (h1 + h2 + h3 + h4) * cadence

            # Fade in and out
            fade_len = int(0.1 * sample_rate)
            if i < fade_len:
                sample_float *= (i / fade_len)
            elif i > num_samples - fade_len:
                sample_float *= ((num_samples - i) / fade_len)

            sample_int = int(sample_float * 24000.0)
            sample_int = max(-32768, min(32767, sample_int))
            frames.extend(struct.pack("<h", sample_int))

        wf.writeframes(frames)


def main():
    ref_dir = ROOT / "voice_service" / "reference"
    test_clips_dir = ROOT / "voice_service" / "test_clips"

    ref_wav = ref_dir / "reference.wav"
    ref_txt = ref_dir / "transcript.txt"
    generate_synthetic_wav(ref_wav, duration_s=7.0, base_freq=180.0)
    ref_txt.write_text("ਸਤਿ ਸ਼੍ਰੀ ਅਕਾਲ ਜੀ, ਵਾਰੀ ਆਟੋਮੇਟਿਡ ਬੁਕਿੰਗ ਸਿਸਟਮ ਵਿੱਚ ਤੁਹਾਡਾ ਸੁਆਗਤ ਹੈ।\n", encoding="utf-8")
    print(f"Generated {ref_wav} and {ref_txt}")

    clips = [
        ("clip1.wav", 5.5, 175.0, "ਮੇਰਾ ਨਾਮ ਕੁਲਦੀਪ ਸਿੰਘ ਹੈ, ਪਿੰਡ ਪਿੰਡ ਕਲਾਂ, ਚਾਰ ਏਕੜ ਸੁਪਰ ਸੀਡਰ ਚਾਹੀਦਾ ਹੈ।"),
        ("clip2.wav", 4.5, 190.0, "ਫੋਨ ਨੰਬਰ ਨੌਂ ਅੱਠ ਸੱਤ ਛੇ ਪੰਜ ਚਾਰ ਤਿੰਨ ਦੋ ਇੱਕ ਜ਼ੀਰੋ।"),
        ("clip3.wav", 3.0, 185.0, "ਹਾਂਜੀ, ਬਿਲਕੁਲ ਠੀਕ ਹੈ।"),
    ]

    for fname, duration, freq, transcript in clips:
        p = test_clips_dir / fname
        generate_synthetic_wav(p, duration_s=duration, base_freq=freq)
        t_path = test_clips_dir / f"{fname}.txt"
        t_path.write_text(transcript + "\n", encoding="utf-8")
        print(f"Generated {p} ({duration}s)")


if __name__ == "__main__":
    main()
