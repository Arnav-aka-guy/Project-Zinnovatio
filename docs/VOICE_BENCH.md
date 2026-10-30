# Voice Model Benchmark (Step V1)

- **Date:** 2026-10-30 19:12:39
- **Device:** CPU (CPU)
- **STT Model:** `ai4bharat/indic-conformer-600m-multilingual`
- **TTS Model:** `ai4bharat/IndicF5`

## 1. Load Times & Memory
- **STT Load Time:** 13.33 s
- **TTS Load Time:** 8.59 s
- **Process Memory (RAM):** 5842 MB
- **GPU Memory Allocated:** 0 MB

## 2. Speech-to-Text (IndicConformer, CTC, language='pa')
| Clip | Duration (s) | Transcript |
| --- | --- | --- |
| clip1.wav | 1.07 |  |
| clip2.wav | 0.59 | ਵ |
| clip3.wav | 0.41 | ਆ ਮੈਂ ਮ ਆ ਮੈਂ ਆ |

## 3. Text-to-Speech (IndicF5)
| Item | Duration (s) | Text |
| --- | --- | --- |
| Sentence 1 (measured 4 steps, est 32 steps) | 230.86 | ਸਤਿ ਸ਼੍ਰੀ ਅਕਾਲ ਜੀ, ਵਾਰੀ ਆਟੋਮੇਟਿਡ ਸਿਸਟਮ ਵਿੱਚ ਤੁਹਾਡਾ ਸੁਆਗਤ ਹੈ। |
| Sentence 2 (measured 4 steps, est 32 steps) | 207.40 | ਕਿਰਪਾ ਕਰਕੇ ਆਪਣਾ ਫ਼ੋਨ ਨੰਬਰ ਅਤੇ ਪਿੰਡ ਦਾ ਨਾਮ ਦੱਸੋ ਜੀ। |
| Sentence 3 (measured 4 steps, est 32 steps) | 212.81 | ਤੁਹਾਡੀ ਸੁਪਰ ਸੀਡਰ ਦੀ ਬੁਕਿੰਗ ਪੰਜ ਨਵੰਬਰ ਲਈ ਪੱਕੀ ਕਰ ਲਈ ਗਈ ਹੈ। |

## 4. Decision & Reply Mode
- **Average TTS Latency:** 217.03 s per sentence
- **Decision:** **CACHED** replies (Threshold: < 5.0 s for LIVE replies; otherwise CACHED)
