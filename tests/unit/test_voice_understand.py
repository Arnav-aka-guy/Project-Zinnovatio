"""Voice engine: Punjabi answers -> booking values, and read-backs that only use real clips."""

from datetime import date

import pytest

from app.voice import catalog
from app.voice.lexicon import NUMBER_WORDS, VILLAGES_PA
from app.voice.understand import normalize, skeleton, understand

TODAY = date(2026, 10, 30)  # a Friday, in the paddy harvest
ALL_CLIPS = {c.id for c in catalog.build_clips()}


def u(step, text, **ctx):
    return understand(step, [text], TODAY, list(VILLAGES_PA), ctx)


def assert_readback_is_real(res):
    assert res.readback, "an accepted answer must be read back"
    for item in res.readback:
        assert item["clip"] in ALL_CLIPS, item["clip"]
    assert res.readback[-1]["clip"] == "prompt/confirm_q"


# ── Phone ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "9876543210",
    "98765 43210",
    "+91 98765 43210",
    "09876543210",
    "੯੮੭੬੫੪੩੨੧੦",
    "ਨੌਂ ਅੱਠ ਸੱਤ ਛੇ ਪੰਜ ਚਾਰ ਤਿੰਨ ਦੋ ਇੱਕ ਜ਼ੀਰੋ",
    "ਅਠਾਨਵੇਂ ਸੱਤ ਛੇ ਪੰਜ ਚਾਰ ਤਿੰਨ ਦੋ ਇੱਕ ਜ਼ੀਰੋ",
    "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ ਮੇਰਾ ਨੰਬਰ 9876543210 ਹੈ",
    "ਬਾਈ ਜੀ 9876543210",
])
def test_phone_accepts_common_ways_of_saying_it(text):
    res = u("phone", text)
    assert res.ok and res.value == "9876543210"
    assert_readback_is_real(res)
    digits = [r["clip"] for r in res.readback if r["clip"].startswith("digit/")]
    assert digits == [f"digit/{d}" for d in "9876543210"]


def test_phone_double_digit_word():
    assert u("phone", "98 double 7 654321").value == "9877654321"


def test_phone_said_in_two_goes():
    first = u("phone", "98765")
    assert not first.ok and first.error_code == "PHONE_TOO_SHORT" and first.partial == "98765"
    assert first.prompt == "prompt/phone_continue"
    second = u("phone", "43210", partial_phone=first.partial)
    assert second.ok and second.value == "9876543210"


@pytest.mark.parametrize("text,code", [
    ("12345 67890", "PHONE_BAD_START"),
    ("98765 43210 12", "PHONE_TOO_LONG"),
    ("ਪਤਾ ਨਹੀਂ", "NOT_UNDERSTOOD"),
])
def test_phone_errors(text, code):
    res = u("phone", text)
    assert not res.ok and res.error_code == code
    assert res.prompt in ALL_CLIPS


# ── Village ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [
    ("ਤਲਵੰਡੀ ਸਾਬੋ", "Talwandi Sabo"),
    ("Talwandi Sabo", "Talwandi Sabo"),
    ("talwandi sabo", "Talwandi Sabo"),
    ("ਮੇਰਾ ਪਿੰਡ ਭੁੱਚੋ ਖੁਰਦ ਹੈ ਜੀ", "Bhucho Khurd"),
    ("ਮੋੜ ਮੰਡੀ", "Maur Mandi"),
    ("ਕੋਟ ਸਮੀਰ", "Kot Shamir"),
    ("ਪਿੰਡ ਕਲਾਂ", "Pind Kalan"),
    ("ਗੋਨਿਆਣਾ", "Goniana Mandi"),
    ("ਰਾਮਪੁਰਾ", "Rampura Phul"),
])
def test_village_matches_gurmukhi_roman_and_aliases(text, expected):
    res = u("village", text)
    assert res.ok and res.value == expected
    assert_readback_is_real(res)


def test_unknown_village_offers_choices():
    res = u("village", "ਲੁਧਿਆਣਾ")
    assert not res.ok and res.error_code == "VILLAGE_NOT_FOUND"
    assert res.prompt == "prompt/village_unknown"


def test_village_from_database_without_gurmukhi_still_matches_by_spelling():
    from app.voice.understand import village_entries

    villages = village_entries(["Jodhpur Romana"])
    res = understand("village", ["ਜੋਧਪੁਰ ਰੋਮਾਣਾ"], TODAY, villages, {})
    assert res.ok and res.value == "Jodhpur Romana"


# ── Acres ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,acres", [
    ("5", 5.0),
    ("5 ਏਕੜ", 5.0),
    ("ਪੰਜ ਏਕੜ", 5.0),
    ("ਸਾਢੇ ਪੰਜ ਏਕੜ", 5.5),
    ("ਪੌਣੇ ਚਾਰ ਕਿੱਲੇ", 3.75),
    ("ਸਵਾ ਤਿੰਨ", 3.25),
    ("ਡੇਢ ਕਿੱਲਾ", 1.5),
    ("ਢਾਈ ਏਕੜ", 2.5),
    ("ਅੱਧਾ ਏਕੜ", 0.5),
    ("ਸਵਾ ਏਕੜ", 1.25),
    ("5 ਕਿੱਲੇ 4 ਕਨਾਲ", 5.5),
    ("2,5", 2.5),
    ("12.75", 12.75),
    ("ਦੋ ਸੌ", 200.0),
    ("ਇੱਕ ਸੌ ਵੀਹ ਏਕੜ", 120.0),
])
def test_acres_punjabi_fractions_and_units(text, acres):
    res = u("acres", text)
    assert res.ok and res.value == acres
    assert_readback_is_real(res)


def test_acres_off_the_quarter_grid_says_about():
    res = u("acres", "5 ਕਿੱਲੇ 3 ਕਨਾਲ")
    assert res.ok and res.value == 5.38
    assert res.readback[0]["clip"] == "prompt/about"


@pytest.mark.parametrize("text,code", [("0.1", "ACRES_TOO_SMALL"), ("300", "ACRES_TOO_LARGE"), ("ਪਤਾ ਨਹੀਂ", "NOT_UNDERSTOOD")])
def test_acres_errors(text, code):
    res = u("acres", text)
    assert not res.ok and res.error_code == code


def test_every_quarter_acre_has_a_spoken_readback():
    for x100 in range(25, 20001, 25):
        for clip in catalog.acres_clips(x100):
            assert clip in ALL_CLIPS, (x100, clip)


# ── Machine ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,mid", [
    ("ਸੁਪਰ ਸੀਡਰ", "super_seeder"),
    ("ਸਾਨੂੰ ਸੁਪਰ ਸੀਡਰ ਚਾਹੀਦਾ ਜੀ", "super_seeder"),
    ("ਹੈਪੀ ਸੀਡਰ", "happy_seeder"),
    ("ਹੈਪੀ", "happy_seeder"),
    ("ਬੇਲਰ", "baler"),
    ("ਪਰਾਲੀ ਦੀਆਂ ਗੱਠਾਂ", "baler"),
    ("ਮਲਚਰ", "mulcher"),
    ("mulcher", "mulcher"),
    ("super_seeder", "super_seeder"),
])
def test_machine(text, mid):
    res = u("machine", text)
    assert res.ok and res.value == mid
    assert_readback_is_real(res)


def test_machine_just_seeder_asks_which():
    res = u("machine", "ਸੀਡਰ")
    assert not res.ok and res.error_code == "MACHINE_WHICH_SEEDER"
    assert [a["value"] for a in res.alternatives] == ["super_seeder", "happy_seeder"]


# ── Date ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,iso", [
    ("ਅੱਜ", "2026-10-30"),
    ("ਕੱਲ੍ਹ ਹੋਈ ਸੀ", "2026-10-29"),
    ("ਕੱਲ੍ਹ ਕੱਟਾਂਗੇ", "2026-10-31"),
    ("15 ਨਵੰਬਰ", "2026-11-15"),
    ("ਪੰਦਰਾਂ ਨਵੰਬਰ", "2026-11-15"),
    ("ਪਹਿਲੀ ਨਵੰਬਰ", "2026-11-01"),
    ("5/11", "2026-11-05"),
    ("2026-11-05", "2026-11-05"),
    ("3 ਦਿਨ ਪਹਿਲਾਂ", "2026-10-27"),
    ("2 ਦਿਨ ਬਾਅਦ", "2026-11-01"),
    ("ਅਗਲੇ ਹਫ਼ਤੇ", "2026-11-06"),
    ("ਐਤਵਾਰ", "2026-11-01"),
    ("ਪਿਛਲੇ ਐਤਵਾਰ ਕੱਟੀ ਸੀ", "2026-10-25"),
    ("ਦੀਵਾਲੀ ਤੋਂ ਦੋ ਦਿਨ ਬਾਅਦ", "2026-11-10"),
    ("ਦੀਵਾਲੀ", "2026-11-08"),
])
def test_date(text, iso):
    res = u("date", text)
    assert res.ok and res.value == iso
    assert_readback_is_real(res)


def test_kal_without_tense_asks_which_one():
    res = u("date", "ਕੱਲ੍ਹ")
    assert not res.ok and res.error_code == "DATE_WHICH_KAL"
    assert [a["value"] for a in res.alternatives] == ["2026-10-29", "2026-10-31"]
    follow = u("date", "ਆਉਣ ਵਾਲਾ", pending="kal")
    assert follow.ok and follow.value == "2026-10-31"


@pytest.mark.parametrize("text", ["ਹਾਲੇ ਨਹੀਂ ਕੱਟਿਆ", "ਪਤਾ ਨਹੀਂ ਜੀ", "ਹਾਲੇ ਪਤਾ ਨਹੀਂ", "not_cut_yet", "don't know"])
def test_not_harvested_yet(text):
    res = u("date", text)
    assert res.ok and res.value == "not_cut_yet"
    assert_readback_is_real(res)


def test_date_far_away_is_refused():
    res = u("date", "15 ਮਾਰਚ")
    assert not res.ok and res.error_code == "DATE_OUT_OF_RANGE"


def test_today_and_tomorrow_are_said_with_the_date():
    clips = [r["clip"] for r in u("date", "ਅੱਜ").readback]
    assert clips == ["prompt/rel_today", "date/10-30", "prompt/confirm_q"]


# ── Yes / no ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,val", [
    ("ਹਾਂ ਜੀ", True), ("ਹਾਂਜੀ", True), ("ਠੀਕ ਹੈ", True), ("ਬਿਲਕੁਲ ਸਹੀ", True), ("yes", True),
    ("ਨਹੀਂ", False), ("ਨਹੀਂ ਜੀ", False), ("ਠੀਕ ਨਹੀਂ", False), ("ਗਲਤ ਹੈ", False),
])
def test_confirm(text, val):
    res = u("confirm", text)
    assert res.ok and res.value is val


def test_confirm_no_with_new_value_is_a_correction():
    res = u("confirm", "ਨਹੀਂ ਜੀ 16 ਨਵੰਬਰ", confirm_step="date")
    assert res.ok and res.value is False
    assert res.correction is not None and res.correction.value == "2026-11-16"


def test_alternatives_are_tried_in_order():
    res = understand("phone", ["ਨੌ ਅੱਠ", "9876543210"], TODAY, None, {})
    assert res.ok and res.value == "9876543210"


def test_empty_speech():
    res = understand("phone", ["  "], TODAY, None, {})
    assert not res.ok and res.error_code == "NO_SPEECH"


# ── Helpers ──────────────────────────────────────────────────────────────
def test_normalize_and_skeleton():
    assert normalize("੧੫ਨਵੰਬਰ।") == "15 ਨਵੰਬਰ"
    assert skeleton("Talwandi Sabo") == skeleton("ਤਲਵੰਡੀ ਸਾਬੋ")
    assert skeleton("Bhucho Khurd") == skeleton("ਭੁੱਚੋ ਖੁਰਦ")


def test_number_table_is_complete():
    assert sorted(NUMBER_WORDS) == list(range(101))
    assert catalog.number_words(150) == "ਇੱਕ ਸੌ ਪੰਜਾਹ"
    assert catalog.acres_words(550) == "ਸਾਢੇ ਪੰਜ ਏਕੜ"
    assert catalog.acres_words(375) == "ਪੌਣੇ ਚਾਰ ਏਕੜ"
    assert catalog.date_words(11, 1) == "ਪਹਿਲੀ ਨਵੰਬਰ"


def test_clip_ids_are_unique_and_texts_present():
    clips = catalog.build_clips()
    ids = [c.id for c in clips]
    assert len(ids) == len(set(ids))
    assert all(c.text.strip() for c in clips)
    for step in catalog.STEPS:
        assert f"prompt/ask_{step}" in ALL_CLIPS
    for day_month in ("date/02-29", "date/12-31", "date/01-01"):
        assert day_month in ALL_CLIPS


# ── English ──────────────────────────────────────────────────────────────
ALL_CLIPS_EN = {c.id for c in catalog.build_clips(lang="en")}


def ue(step, text, **ctx):
    return understand(step, [text], TODAY, list(VILLAGES_PA), ctx, "en")


def assert_en_readback_is_real(res):
    assert res.readback
    for item in res.readback:
        assert item["clip"] in ALL_CLIPS_EN, item["clip"]


@pytest.mark.parametrize("text,value", [
    ("nine eight seven six five four three two one zero", "9876543210"),
    ("my number is ninety eight seventy six five four three two one zero", "9876543210"),
    ("double nine eight seven six five four three two one", "9987654321"),
])
def test_english_phone(text, value):
    res = ue("phone", text)
    assert res.ok and res.value == value
    assert_en_readback_is_real(res)


@pytest.mark.parametrize("text,expected", [
    ("Talwandi Sabo", "Talwandi Sabo"),
    ("my village is bhucho khurd", "Bhucho Khurd"),
    ("Gonyana mandi", "Goniana Mandi"),
])
def test_english_village(text, expected):
    res = ue("village", text)
    assert res.ok and res.value == expected
    assert_en_readback_is_real(res)


@pytest.mark.parametrize("text,acres", [
    ("five acres", 5.0),
    ("five and a half acres", 5.5),
    ("5 acres and a half", 5.5),
    ("half an acre", 0.5),
    ("three quarters of an acre", 0.75),
    ("two point five", 2.5),
    ("one hundred and twenty acres", 120.0),
    ("twenty five", 25.0),
    ("an acre", 1.0),
    ("one and a half", 1.5),
])
def test_english_acres(text, acres):
    res = ue("acres", text)
    assert res.ok and res.value == acres
    assert_en_readback_is_real(res)


def test_english_acres_readback_word_order():
    # Off the own-clip grid: "45 acres" + "and a quarter" in English, "ਸਵਾ" + "ਪੰਤਾਲੀ ਏਕੜ" in Punjabi.
    assert [r["clip"] for r in ue("acres", "45 and a quarter").readback][:2] == ["acres/4500", "prompt/and_quarter"]
    assert [r["clip"] for r in u("acres", "45.25").readback][:2] == ["prompt/frac_sava", "acres/4500"]
    for x100 in range(25, 20001, 25):
        for clip in catalog.acres_clips(x100, "en"):
            assert clip in ALL_CLIPS_EN, (x100, clip)


@pytest.mark.parametrize("text,mid", [
    ("super seeder", "super_seeder"), ("I need a happy seeder", "happy_seeder"),
    ("super cedar", "super_seeder"), ("baler", "baler"), ("mulcher please", "mulcher"),
])
def test_english_machine(text, mid):
    res = ue("machine", text)
    assert res.ok and res.value == mid


@pytest.mark.parametrize("text,iso", [
    ("today", "2026-10-30"),
    ("tomorrow", "2026-10-31"),
    ("yesterday", "2026-10-29"),
    ("day after tomorrow", "2026-11-01"),
    ("15th November", "2026-11-15"),
    ("November 15", "2026-11-15"),
    ("the 1st of November", "2026-11-01"),
    ("fifteenth november", "2026-11-15"),
    ("3 days ago", "2026-10-27"),
    ("in 2 days", "2026-11-01"),
    ("next week", "2026-11-06"),
    ("last Sunday", "2026-10-25"),
    ("next monday", "2026-11-02"),
    ("two days after diwali", "2026-11-10"),
    ("not harvested yet", "not_cut_yet"),
    ("don't know yet", "not_cut_yet"),
])
def test_english_date(text, iso):
    res = ue("date", text)
    assert res.ok and res.value == iso
    assert_en_readback_is_real(res)


@pytest.mark.parametrize("text,val", [
    ("yes", True), ("yeah that's right", True), ("correct", True), ("ok", True),
    ("no", False), ("not correct", False), ("nope", False),
])
def test_english_confirm(text, val):
    res = ue("confirm", text)
    assert res.ok and res.value is val


def test_english_and_punjabi_clip_sets_have_the_same_ids_except_word_order_pieces():
    pa = {c.id for c in catalog.build_clips(lang="pa")}
    en = ALL_CLIPS_EN
    assert pa - en == {f"prompt/{k}" for k in catalog.PA_ONLY_PROMPTS}
    assert en - pa == {f"prompt/{k}" for k in catalog.EN_ONLY_PROMPTS}
    texts = {c.id: c.text for c in catalog.build_clips(lang="en")}
    assert texts["date/11-15"] == "15th November" and texts["date/11-01"] == "1st November"
    assert texts["acres/550"] == "5 and a half acres" and texts["digit/0"] == "zero"
