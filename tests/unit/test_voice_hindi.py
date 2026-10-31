"""Hindi answers: understood in every mode, read back in Hindi, and the Hindi voice script is complete."""

from datetime import date

import pytest

from app.voice import catalog
from app.voice.lexicon import deva_to_guru, guru_to_deva
from app.voice.understand import understand

TODAY = date(2026, 10, 31)  # a Saturday


@pytest.mark.parametrize(
    ("step", "said", "value"),
    [
        ("phone", "नौ आठ सात छह पाँच चार तीन दो एक शून्य", "9876543210"),
        ("phone", "मेरा नंबर 98765 43210 है", "9876543210"),
        ("phone", "nau aath saat chhe paanch char teen do ek shunya", "9876543210"),
        ("phone", "९८७६५४३२१०", "9876543210"),
        ("acres", "साढ़े पाँच एकड़", 5.5),
        ("acres", "पौने चार एकड़", 3.75),
        ("acres", "पंद्रह किल्ले", 15.0),
        ("acres", "dhai ekad", 2.5),
        ("acres", "ਪਾਂਚ ਏਕੜ", 5.0),  # Hindi word heard by the Punjabi recogniser
        ("acres", "सत्ताईस एकड़", 27.0),
        ("machine", "हैप्पी सीडर चाहिए", "happy_seeder"),
        ("machine", "मुझे बेलर चाहिए", "baler"),
        ("machine", "मल्चर", "mulcher"),
        ("date", "कल कटाई हो गई थी", "2026-10-30"),
        ("date", "कल काटेंगे", "2026-11-01"),
        ("date", "परसों करेंगे", "2026-11-02"),
        ("date", "पंद्रह नवंबर", "2026-11-15"),
        ("date", "आज", "2026-10-31"),
        ("date", "पता नहीं", "not_cut_yet"),
        ("date", "agle somvar", "2026-11-02"),
        ("village", "तलवंडी साबो", "Talwandi Sabo"),
        ("village", "मौड़ मंडी गांव", "Maur Mandi"),
        ("village", "भुच्चो खुर्द", "Bhucho Khurd"),
        ("confirm", "हाँ जी", True),
        ("confirm", "जी हां बिल्कुल", True),
        ("confirm", "नहीं", False),
        ("confirm", "haan ji", True),
    ],
)
def test_hindi_answers_are_understood(step, said, value):
    u = understand(step, [said], TODAY, lang="hi")
    assert u.ok, (said, u.error_code)
    assert u.value == value


@pytest.mark.parametrize("lang", ["pa", "en", "hi"])
def test_hindi_is_understood_in_every_mode(lang):
    assert understand("acres", ["साढ़े पाँच एकड़"], TODAY, lang=lang).value == 5.5


def test_hindi_display_and_readback():
    u = understand("date", ["पंद्रह नवंबर"], TODAY, lang="hi")
    assert u.display_hi == "15 नवंबर 2026 (रविवार)"
    assert u.as_dict()["display_hi"] == "15 नवंबर 2026 (रविवार)"
    acres = understand("acres", ["सवा पाँच एकड़"], TODAY, lang="hi")
    assert acres.display_hi == "5.25 एकड़"
    assert [i["clip"] for i in acres.readback] == ["acres/525", "prompt/confirm_q"]
    village = understand("village", ["Talwandi Sabo"], TODAY, lang="hi")
    assert village.display_hi == "तलवंडी साबो"
    assert understand("machine", ["baler"], TODAY, lang="hi").display_hi == "बेलर"


def test_punjabi_and_english_still_work():
    assert understand("acres", ["ਸਾਢੇ ਪੰਜ ਏਕੜ"], TODAY).value == 5.5
    assert understand("acres", ["five and a half acres"], TODAY, lang="en").value == 5.5
    assert understand("confirm", ["ਹਾਂ ਜੀ"], TODAY).value is True


def test_script_converters():
    assert deva_to_guru("पाँच एकड़") == "ਪਾਂਚ ਏਕੜ"
    assert deva_to_guru("Pind Kalan 5") == "Pind Kalan 5"
    assert guru_to_deva("ਤਲਵੰਡੀ ਸਾਬੋ") == "तलवंडी साबो"
    assert guru_to_deva("ਭੁੱਚੋ ਖੁਰਦ") == "भुच्चो खुरद"


def test_hindi_voice_script_is_complete():
    assert set(catalog.PROMPTS_HI) == set(catalog.PROMPTS)
    hi = {c.id: c.text for c in catalog.build_clips(lang="hi")}
    pa = {c.id for c in catalog.build_clips(lang="pa")}
    assert set(hi) == pa  # same clip ids, so read-backs work in every language
    assert hi["acres/550"] == "साढ़े पाँच एकड़"
    assert hi["acres/275"] == "पौने तीन एकड़"
    assert hi["date/11-15"] == "पंद्रह नवंबर"
    assert hi["digit/0"] == "शून्य"
    assert all(any("ऀ" <= ch <= "ॿ" for ch in text) for text in hi.values())
