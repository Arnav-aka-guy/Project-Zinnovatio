# Voice Booking Evaluation Report

**Date**: 2026-10-30T14:46:04Z  
**Pass Bar**: 100% on the 5 realistic farmer dialogues  
**Result**: **100.0% (5/5 passed)**  

## 1. Dialogue Evaluation Results

| ID | Dialogue Title | Turns | Status | Extracted Result |
|:---|:---------------|:-----:|:------:|:-----------------|
| 1 | Super Seeder Standard Happy Path | 6 | ✅ PASS | Confirmed: 9876543210, Rampur, 2.5ac, Super Seeder |
| 2 | Happy Seeder Multi-field Turn and Explicit Date | 2 | ✅ PASS | Confirmed: 9812345678, Kila Raipur, 5.0ac, Happy Seeder |
| 3 | Noisy Speech Retry and In-Sentence Acres Correction | 7 | ✅ PASS | Confirmed: 9888877777, Dhandra, 4.0ac, Super Seeder |
| 4 | Read-Back Summary Date Revision | 7 | ✅ PASS | Confirmed: 9777766666, Mansuran, 1.5ac, Mulcher |
| 5 | Voluntary Cancellation Midway | 3 | ✅ PASS | Cancelled: 9855544433, Jodhan, —ac, — |

## 2. Speech Models & Infrastructure

- **Local Voice Service Status**: `Offline / Standalone Mode`
- **Speech-to-Text Model**: AI4Bharat IndicConformer (`ai4bharat/indic-conformer-600m-multilingual`, language `pa`)
- **Text-to-Speech Model**: AI4Bharat IndicF5 (`ai4bharat/IndicF5`, pre-cached 16 prompts)
- **Understanding Engine**: Deterministic Python regex and fuzzy matching (app/voice/understand.py, zero LLM reliance)
- **Latency Benchmarks** (from `docs/VOICE_BENCH.md`):
  - IndicConformer STT: **~1.03s** on CPU
  - IndicF5 TTS (Pre-cached WAVs): **< 2ms** response time

## 3. Evaluation Criteria

1. **Phone Number Accuracy**: Must correctly resolve 10-digit Indian numbers across Gurmukhi digits, words, and English transliterations.
2. **Fractional Acres**: Must properly map fractional units (ਢਾਈ=2.5, ਡੇਢ=1.5, ਸਾਢੇ=X+0.5, ਸਵਾ=X+0.25, ਪੌਣੇ=X-0.25).
3. **Self-Correction**: If a farmer corrects an acre count or date mid-sentence or in subsequent turns, the updated value must supersede earlier tokens.
4. **Confirmation Gate**: Bookings are never created without affirmative confirmation (`ਹਾਂਜੀ` / `yes` or button tap).
5. **Cancellation**: Farmer request to cancel immediately sets session to cancelled and drops draft state.
