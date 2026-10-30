"""Unit tests for deterministic Punjabi voice understanding (Step V5).

Covers 30+ comprehensive test cases for:
  - Phone numbers (Gurmukhi digits, words, English, double/triple idioms)
  - Land acres (fractions: ਢਾਈ, ਡੇਢ, ਸਾਢੇ, ਸਵਾ, ਪੌਣੇ, words, digits)
  - Machine canonicalization
  - Date extraction (relative days, weekdays, explicit dates)
  - Village fuzzy matching
  - Yes/No confirmation intents
  - Multi-field spoken turns
"""

import datetime

from app.voice.understand import (
    extract_acres,
    extract_confirmation,
    extract_date,
    extract_machine,
    extract_phone,
    extract_village,
    understand_voice_turn,
)

# Fixed reference base date for testing relative dates (2026-11-01, a Sunday)
BASE_DATE = datetime.date(2026, 11, 1)


# ── 1. Phone Numbers ─────────────────────────────────────────────────────────

def test_phone_gurmukhi_digits():
    assert extract_phone("ਮੇਰਾ ਨੰਬਰ ੯੮੭੬੫੪੩੨੧੦ ਹੈ") == "9876543210"


def test_phone_punjabi_words():
    # ਨੌਂ ਅੱਠ ਸੱਤ ਛੇ ਪੰਜ ਚਾਰ ਤਿੰਨ ਦੋ ਇੱਕ ਜ਼ੀਰੋ
    assert extract_phone("ਨੌਂ ਅੱਠ ਸੱਤ ਛੇ ਪੰਜ ਚਾਰ ਤਿੰਨ ਦੋ ਇੱਕ ਜ਼ੀਰੋ") == "9876543210"


def test_phone_english_words():
    assert extract_phone("my mobile is nine eight seven six five four three two one zero") == "9876543210"


def test_phone_gurmukhi_english_transliteration():
    # ਨਾਈਨ ਏਟ ਸੈਵਨ ਸਿਕਸ ਫ਼ਾਈਵ ਫ਼ੋਰ ਥ੍ਰੀ ਟੂ ਵਨ ਜ਼ੀਰੋ
    assert extract_phone("ਨਾਈਨ ਏਟ ਸੈਵਨ ਸਿਕਸ ਫ਼ਾਈਵ ਫ਼ੋਰ ਥ੍ਰੀ ਟੂ ਵਨ ਜ਼ੀਰੋ") == "9876543210"


def test_phone_double_idiom():
    # ਡਬਲ ਨੌਂ = 99
    assert extract_phone("ਡਬਲ ਨੌਂ ਅੱਠ ਸੱਤ ਛੇ ਪੰਜ ਚਾਰ ਤਿੰਨ ਦੋ ਇੱਕ") == "9987654321"


def test_phone_triple_idiom():
    # ਟ੍ਰਿਪਲ ਨੌਂ = 999
    assert extract_phone("ਟ੍ਰਿਪਲ ਨੌਂ ਅੱਠ ਸੱਤ ਛੇ ਪੰਜ ਚਾਰ ਤਿੰਨ ਦੋ") == "9998765432"


def test_phone_with_leading_91():
    assert extract_phone("ਨੰਬਰ ਹੈ 919876543210") == "9876543210"


def test_phone_with_leading_zero():
    assert extract_phone("ਫ਼ੋਨ 09876543210 ਲਿਖ ਲਵੋ") == "9876543210"


def test_phone_invalid_short():
    assert extract_phone("ਸਿਰਫ਼ 98765 ਨੰਬਰ ਹੈ") is None


# ── 2. Acres & Fractions ─────────────────────────────────────────────────────

def test_acres_dhaai():
    # ਢਾਈ = 2.5
    assert extract_acres("ਮੇਰੇ ਕੋਲ ਢਾਈ ਏਕੜ ਜ਼ਮੀਨ ਹੈ") == 2.5


def test_acres_dedh():
    # ਡੇਢ = 1.5
    assert extract_acres("ਡੇਢ ਕਿੱਲੇ ਵਾਹੁਣੇ ਹਨ") == 1.5


def test_acres_saadhe_three():
    # ਸਾਢੇ ਤਿੰਨ = 3.5
    assert extract_acres("ਸਾਢੇ ਤਿੰਨ ਏਕੜ") == 3.5


def test_acres_saadhe_four():
    # ਸਾਢੇ 4 = 4.5
    assert extract_acres("ਸਾਢੇ 4 ਏਕੜ ਜ਼ਮੀਨ") == 4.5


def test_acres_sawa_two():
    # ਸਵਾ ਦੋ = 2.25
    assert extract_acres("ਸਵਾ ਦੋ ਕਿੱਲੇ") == 2.25


def test_acres_paune_four():
    # ਪੌਣੇ ਚਾਰ = 3.75
    assert extract_acres("ਪੌਣੇ ਚਾਰ ਏਕੜ") == 3.75


def test_acres_adha():
    # ਅੱਧਾ = 0.5
    assert extract_acres("ਅੱਧਾ ਏਕੜ ਹੈ ਜੀ") == 0.5


def test_acres_gurmukhi_digits():
    assert extract_acres("੫ ਏਕੜ") == 5.0


def test_acres_word_ten():
    assert extract_acres("ਦਸ ਕਿੱਲੇ") == 10.0


def test_acres_decimal_ascii():
    assert extract_acres("25.5 acres") == 25.5


# ── 3. Machine Types ─────────────────────────────────────────────────────────

def test_machine_super_seeder_punjabi():
    assert extract_machine("ਸਾਨੂੰ ਸੁਪਰ ਸੀਡਰ ਚਾਹੀਦਾ ਹੈ") == "Super Seeder"


def test_machine_super_seeder_english():
    assert extract_machine("need super seeder machine") == "Super Seeder"


def test_machine_happy_seeder():
    assert extract_machine("ਹੈਪੀ ਸੀਡਰ ਭੇਜ ਦਿਓ") == "Happy Seeder"


def test_machine_zero_drill():
    assert extract_machine("ਜ਼ੀਰੋ ਡਰਿੱਲ ਦੀ ਲੋੜ ਹੈ") == "Zero Till Drill"


def test_machine_mulcher():
    assert extract_machine("ਮਲਚਰ ਚਾਹੀਦਾ ਹੈ ਜੀ") == "Mulcher"


def test_machine_rotavator():
    assert extract_machine("ਰੋਟਾਵੇਟਰ ਲੈਣਾ ਹੈ") == "Rotavator"


def test_machine_baler():
    assert extract_machine("ਬੇਲਰ ਮਸ਼ੀਨ ਭੇਜੋ") == "Baler"


# ── 4. Harvest / Required Dates ──────────────────────────────────────────────

def test_date_today():
    # Base date 2026-11-01
    assert extract_date("ਮਸ਼ੀਨ ਅੱਜ ਹੀ ਚਾਹੀਦੀ ਹੈ", base_date=BASE_DATE) == "2026-11-01"


def test_date_tomorrow():
    assert extract_date("ਕੱਲ੍ਹ ਨੂੰ ਲੈ ਕੇ ਆਉਣਾ", base_date=BASE_DATE) == "2026-11-02"


def test_date_day_after_tomorrow():
    assert extract_date("ਪਰਸੋਂ ਤੱਕ ਫ਼ਸਲ ਕੱਟੀ ਜਾਵੇਗੀ", base_date=BASE_DATE) == "2026-11-03"


def test_date_weekday():
    # Base date is Sunday (2026-11-01), so Monday is 2026-11-02
    assert extract_date("ਸੋਮਵਾਰ ਨੂੰ ਮਸ਼ੀਨ ਭੇਜ ਦੇਣਾ", base_date=BASE_DATE) == "2026-11-02"


def test_date_explicit_month_day():
    # ੫ ਨਵੰਬਰ = 2026-11-05
    assert extract_date("੫ ਨਵੰਬਰ ਲਈ ਬੁੱਕ ਕਰ ਦਿਓ", base_date=BASE_DATE) == "2026-11-05"


def test_date_explicit_tareekh():
    # 10 ਤਾਰੀਖ਼
    assert extract_date("10 ਤਾਰੀਖ਼ ਨੂੰ ਚਾਹੀਦੀ ਹੈ", base_date=BASE_DATE) == "2026-11-10"


# ── 5. Village Names ─────────────────────────────────────────────────────────

def test_village_direct_match():
    assert extract_village("ਮੇਰਾ ਪਿੰਡ ਰਾਮਪੁਰ ਹੈ") == "Rampur"


def test_village_fuzzy_match():
    # Typo: Ramppur -> Rampur
    assert extract_village("ਪਿੰਡ Ramppur ਤੋਂ ਹਾਂ") == "Rampur"


def test_village_punjabi_name():
    assert extract_village("ਅਸੀਂ ਭਾਦਸੋਂ ਵਿੱਚ ਰਹਿੰਦੇ ਹਾਂ") == "Bhadson"


# ── 6. Confirmation Intents ──────────────────────────────────────────────────

def test_confirmation_yes_punjabi():
    assert extract_confirmation("ਹਾਂਜੀ ਬਿਲਕੁਲ ਸਹੀ ਹੈ") is True


def test_confirmation_yes_short():
    assert extract_confirmation("ਹਾਂ") is True


def test_confirmation_yes_english():
    assert extract_confirmation("yes this is correct") is True


def test_confirmation_no_punjabi():
    assert extract_confirmation("ਨਹੀਂ ਜੀ ਗ਼ਲਤ ਹੈ") is False


def test_confirmation_no_english():
    assert extract_confirmation("no cancel it") is False


# ── 7. Multi-field Combined Spoken Turns ─────────────────────────────────────

def test_understand_complete_turn():
    turn_text = "ਮੇਰਾ ਫ਼ੋਨ 9876543210 ਹੈ, ਪਿੰਡ ਰਾਮਪੁਰ, ਢਾਈ ਏਕੜ ਲਈ ਸੁਪਰ ਸੀਡਰ ਚਾਹੀਦਾ ਹੈ ਕੱਲ੍ਹ ਨੂੰ"
    res = understand_voice_turn(turn_text, base_date=BASE_DATE)
    assert res.phone == "9876543210"
    assert res.village == "Rampur"
    assert res.acres == 2.5
    assert res.machine == "Super Seeder"
    assert res.harvest_date == "2026-11-02"
    assert res.confidence == "high"
    assert len(res.missing_fields) == 0


def test_understand_single_field_phone():
    res = understand_voice_turn("9876543210", expected_field="phone")
    assert res.phone == "9876543210"
    assert res.confidence == "high"
    assert "village" in res.missing_fields
