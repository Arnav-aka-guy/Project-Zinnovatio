"""The voice script: every clip the voice booking flow can play.

One clip = one id + the exact Punjabi sentence spoken for it. The generator
(`scripts/make_voice_clips.py`) turns this list into audio files under
`web/public/audio/pa/`, and the engine (`app/voice/understand.py`) answers
with lists of these ids, so the two can never drift apart.

Clip id rules (the frontend relies on them):
  prompt/<key>        fixed sentences (questions, retries, outcomes)
  digit/<0-9>         single digits, for reading back a phone number
  village/<slug>      a village name
  machine/<service>   a machine name
  acres/<x100>        an acreage, e.g. acres/550 = "ਸਾਢੇ ਪੰਜ ਏਕੜ"
  date/<MM-DD>        a calendar date, e.g. date/11-15 = "ਪੰਦਰਾਂ ਨਵੰਬਰ"
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.voice.lexicon import MACHINES, MONTH_WORDS, NUMBER_WORDS, VILLAGES_PA, VillageEntry

# key -> (Punjabi, English). The Punjabi line is what the voice says.
# Written as one breath each: few commas, so the voice does not pause mid-line.
PROMPTS: dict[str, tuple[str, str]] = {
    "welcome": (
        "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ! ਵਾਰੀ ਵਿੱਚ ਤੁਹਾਡਾ ਸਵਾਗਤ ਹੈ। ਬੱਸ ਪੰਜ ਸਵਾਲਾਂ ਵਿੱਚ ਤੁਹਾਡੀ ਮਸ਼ੀਨ ਦੀ ਵਾਰੀ ਬੁੱਕ ਹੋ ਜਾਵੇਗੀ।",
        "Sat Sri Akal! Welcome to Vaari. Five quick questions and your machine turn is booked.",
    ),
    # Questions, one per step.
    "ask_phone": (
        "ਕਿਰਪਾ ਕਰਕੇ ਆਪਣਾ ਦਸ ਅੰਕਾਂ ਦਾ ਮੋਬਾਈਲ ਨੰਬਰ ਦੱਸੋ ਜੀ।",
        "Please tell me your 10-digit mobile number.",
    ),
    "ask_village": (
        "ਤੁਹਾਡਾ ਖੇਤ ਕਿਹੜੇ ਪਿੰਡ ਵਿੱਚ ਹੈ ਜੀ? ਪਿੰਡ ਦਾ ਨਾਂ ਦੱਸੋ।",
        "Which village is your field in? Say the village name.",
    ),
    "ask_acres": (
        "ਕਿੰਨੇ ਏਕੜ ਵਿੱਚ ਕੰਮ ਕਰਵਾਉਣਾ ਹੈ ਜੀ? ਜਿਵੇਂ ਪੰਜ ਏਕੜ ਜਾਂ ਸਾਢੇ ਤਿੰਨ ਏਕੜ।",
        "How many acres need the machine? For example 5 acres or 3 and a half acres.",
    ),
    "ask_machine": (
        "ਤੁਹਾਨੂੰ ਕਿਹੜੀ ਮਸ਼ੀਨ ਚਾਹੀਦੀ ਹੈ ਜੀ? ਸੁਪਰ ਸੀਡਰ ਹੈਪੀ ਸੀਡਰ ਬੇਲਰ ਜਾਂ ਮਲਚਰ?",
        "Which machine do you need? Super Seeder, Happy Seeder, Baler or Mulcher?",
    ),
    "ask_date": (
        "ਝੋਨੇ ਦੀ ਕਟਾਈ ਕਦੋਂ ਹੋਈ ਹੈ ਜਾਂ ਕਦੋਂ ਹੋਣੀ ਹੈ ਜੀ? ਜਿਵੇਂ ਅੱਜ ਕੱਲ੍ਹ ਜਾਂ ਪੰਦਰਾਂ ਨਵੰਬਰ। ਜੇ ਪਤਾ ਨਹੀਂ ਤਾਂ ਕਹੋ ਪਤਾ ਨਹੀਂ।",
        "When was or when will the paddy be harvested? For example today, tomorrow or 15 November. If you don't know, say 'don't know'.",
    ),
    "ask_consent": (
        "ਤੁਹਾਡਾ ਨੰਬਰ ਤੇ ਖੇਤ ਦੀ ਜਾਣਕਾਰੀ ਸਿਰਫ਼ ਮਸ਼ੀਨ ਦੀ ਵਾਰੀ ਅਤੇ ਕੰਮ ਦੇ ਰਿਕਾਰਡ ਲਈ ਵਰਤੀ ਜਾਵੇਗੀ। ਕੀ ਬੁਕਿੰਗ ਪੱਕੀ ਕਰ ਦੇਈਏ ਜੀ?",
        "Your number and field details are used only for the machine turn and the work record. Shall we confirm the booking?",
    ),
    # Read-back pieces.
    "rb_phone": ("ਤੁਹਾਡਾ ਨੰਬਰ ਹੈ", "Your number is"),
    "confirm_q": ("ਕੀ ਇਹ ਠੀਕ ਹੈ ਜੀ?", "Is this correct?"),
    "rel_today": ("ਅੱਜ", "Today"),
    "rel_yesterday": ("ਬੀਤਿਆ ਕੱਲ੍ਹ", "Yesterday"),
    "rel_tomorrow": ("ਆਉਣ ਵਾਲਾ ਕੱਲ੍ਹ", "Tomorrow"),
    "date_not_yet": ("ਕਟਾਈ ਦੀ ਤਾਰੀਖ਼ ਹਾਲੇ ਪੱਕੀ ਨਹੀਂ।", "Harvest date not fixed yet."),
    "frac_sava": ("ਸਵਾ", "and a quarter"),
    "frac_saadhe": ("ਸਾਢੇ", "and a half"),
    "frac_paune": ("ਪੌਣੇ", "less a quarter"),
    "and_quarter": ("ਅਤੇ ਚੌਥਾਈ", "and a quarter"),
    "and_half": ("ਅਤੇ ਅੱਧਾ", "and a half"),
    "and_three_quarters": ("ਅਤੇ ਪੌਣਾ", "and three quarters"),
    "about": ("ਲਗਭਗ", "about"),
    "ok_next": ("ਠੀਕ ਹੈ ਜੀ।", "Okay."),
    # Retries.
    "retry_generic": ("ਮਾਫ਼ ਕਰਨਾ ਜੀ ਗੱਲ ਸਮਝ ਨਹੀਂ ਆਈ। ਇੱਕ ਵਾਰ ਫਿਰ ਬੋਲੋ ਜੀ।", "Sorry, I did not get that. Please say it again."),
    "no_speech": ("ਕੋਈ ਆਵਾਜ਼ ਨਹੀਂ ਆਈ ਜੀ। ਮਾਈਕ ਦਬਾ ਕੇ ਫਿਰ ਬੋਲੋ।", "I heard nothing. Tap the mic and speak again."),
    "phone_short": ("ਨੰਬਰ ਪੂਰਾ ਨਹੀਂ ਆਇਆ ਜੀ। ਦਸੇ ਅੰਕ ਹੌਲੀ ਹੌਲੀ ਦੁਬਾਰਾ ਬੋਲੋ।", "The number is incomplete. Say all ten digits slowly."),
    "phone_continue": ("ਠੀਕ ਹੈ ਜੀ। ਹੁਣ ਬਾਕੀ ਅੰਕ ਬੋਲੋ।", "Okay. Now say the remaining digits."),
    "phone_long": ("ਨੰਬਰ ਵਿੱਚ ਦਸ ਤੋਂ ਵੱਧ ਅੰਕ ਆ ਗਏ ਜੀ। ਸਿਰਫ਼ ਦਸ ਅੰਕ ਦੁਬਾਰਾ ਬੋਲੋ।", "That has more than ten digits. Say just the ten digits again."),
    "phone_start": ("ਮੋਬਾਈਲ ਨੰਬਰ ਛੇ ਸੱਤ ਅੱਠ ਜਾਂ ਨੌਂ ਨਾਲ ਸ਼ੁਰੂ ਹੁੰਦਾ ਹੈ ਜੀ। ਨੰਬਰ ਦੁਬਾਰਾ ਬੋਲੋ।", "A mobile number starts with 6, 7, 8 or 9. Say it again."),
    "village_unknown": ("ਇਹ ਪਿੰਡ ਸੂਚੀ ਵਿੱਚ ਨਹੀਂ ਮਿਲਿਆ ਜੀ। ਨਾਂ ਦੁਬਾਰਾ ਬੋਲੋ ਜਾਂ ਹੇਠਾਂ ਸੂਚੀ ਵਿੱਚੋਂ ਚੁਣੋ।", "That village is not on the list. Say it again or pick from the list below."),
    "acres_unknown": ("ਏਕੜ ਸਮਝ ਨਹੀਂ ਆਏ ਜੀ। ਜਿਵੇਂ ਬੋਲੋ ਪੰਜ ਏਕੜ।", "I did not get the acres. Say, for example, 5 acres."),
    "acres_range": ("ਏਕੜ ਚੌਥਾਈ ਤੋਂ ਦੋ ਸੌ ਦੇ ਵਿੱਚ ਹੋਣੇ ਚਾਹੀਦੇ ਹਨ ਜੀ। ਦੁਬਾਰਾ ਦੱਸੋ।", "Acres must be between a quarter and 200. Please say again."),
    "machine_unknown": ("ਮਸ਼ੀਨ ਦਾ ਨਾਂ ਸਮਝ ਨਹੀਂ ਆਇਆ ਜੀ। ਸੁਪਰ ਸੀਡਰ ਹੈਪੀ ਸੀਡਰ ਬੇਲਰ ਜਾਂ ਮਲਚਰ ਵਿੱਚੋਂ ਇੱਕ ਬੋਲੋ।", "I did not get the machine. Say Super Seeder, Happy Seeder, Baler or Mulcher."),
    "machine_which_seeder": ("ਸੁਪਰ ਸੀਡਰ ਚਾਹੀਦਾ ਹੈ ਜਾਂ ਹੈਪੀ ਸੀਡਰ ਜੀ?", "Super Seeder or Happy Seeder?"),
    "date_unknown": ("ਤਾਰੀਖ਼ ਸਮਝ ਨਹੀਂ ਆਈ ਜੀ। ਜਿਵੇਂ ਬੋਲੋ ਅੱਜ ਕੱਲ੍ਹ ਜਾਂ ਪੰਦਰਾਂ ਨਵੰਬਰ।", "I did not get the date. Say today, tomorrow or 15 November."),
    "date_range": ("ਇਹ ਤਾਰੀਖ਼ ਬਹੁਤ ਦੂਰ ਹੈ ਜੀ। ਦੋ ਮਹੀਨਿਆਂ ਦੇ ਅੰਦਰ ਦੀ ਤਾਰੀਖ਼ ਦੱਸੋ।", "That date is too far. Give a date within two months."),
    "date_which_kal": ("ਬੀਤਿਆ ਕੱਲ੍ਹ ਜਾਂ ਆਉਣ ਵਾਲਾ ਕੱਲ੍ਹ ਜੀ?", "Yesterday or tomorrow?"),
    "confirm_unknown": ("ਹਾਂ ਜਾਂ ਨਹੀਂ ਵਿੱਚ ਜਵਾਬ ਦਿਓ ਜੀ।", "Please answer yes or no."),
    "say_again": ("ਠੀਕ ਹੈ ਜੀ ਫਿਰ ਤੋਂ ਦੱਸੋ।", "Okay, tell me again."),
    "mic_off": ("ਮਾਈਕ ਬੰਦ ਹੈ ਜੀ। ਤੁਸੀਂ ਹੇਠਾਂ ਲਿਖ ਕੇ ਵੀ ਜਵਾਬ ਦੇ ਸਕਦੇ ਹੋ।", "The mic is off. You can type your answer below."),
    # Outcomes after saving.
    "done_sched_pre": ("ਤੁਹਾਡੀ ਵਾਰੀ ਲੱਗ ਗਈ ਹੈ ਜੀ। ਮਸ਼ੀਨ", "Your turn is booked. The machine will come to your field on"),
    "done_sched_post": ("ਨੂੰ ਤੁਹਾਡੇ ਖੇਤ ਆਵੇਗੀ। ਧੰਨਵਾਦ ਜੀ।", "Thank you."),
    "done_open": ("ਤੁਹਾਡੀ ਬੇਨਤੀ ਦਰਜ ਹੋ ਗਈ ਹੈ ਜੀ। ਵਾਰੀ ਲੱਗਣ ਤੇ ਸੈਂਟਰ ਤੋਂ ਤੁਹਾਨੂੰ ਦੱਸਿਆ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ।", "Your request is saved. The centre will tell you when your turn is fixed. Thank you."),
    "done_needs_info": ("ਤੁਹਾਡੀ ਬੇਨਤੀ ਦਰਜ ਹੋ ਗਈ ਹੈ ਜੀ। ਕਟਾਈ ਦੀ ਤਾਰੀਖ਼ ਪੱਕੀ ਹੋਣ ਤੇ ਵਾਰੀ ਲੱਗੇਗੀ। ਧੰਨਵਾਦ ਜੀ।", "Your request is saved. The turn is fixed once the harvest date is known. Thank you."),
    "done_will_miss": ("ਤੁਹਾਡੀ ਬੇਨਤੀ ਦਰਜ ਹੋ ਗਈ ਹੈ ਜੀ ਪਰ ਹਾਲੇ ਸਮੇਂ ਸਿਰ ਮਸ਼ੀਨ ਖ਼ਾਲੀ ਨਹੀਂ ਹੈ। ਸੈਂਟਰ ਵਾਲੇ ਤੁਹਾਡੇ ਨਾਲ ਜਲਦੀ ਗੱਲ ਕਰਨਗੇ।", "Your request is saved, but no machine is free in time yet. The centre will call you soon."),
    "submit_failed": ("ਮਾਫ਼ ਕਰਨਾ ਜੀ ਬੁਕਿੰਗ ਸੇਵ ਨਹੀਂ ਹੋਈ। ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ ਜਾਂ ਸੈਂਟਰ ਤੇ ਗੱਲ ਕਰੋ।", "Sorry, the booking was not saved. Try again or talk to the centre."),
    "booking_cancelled": ("ਠੀਕ ਹੈ ਜੀ ਬੁਕਿੰਗ ਨਹੀਂ ਕੀਤੀ। ਕੋਈ ਜਾਣਕਾਰੀ ਬਦਲਣੀ ਹੋਵੇ ਤਾਂ ਉੱਪਰੋਂ ਚੁਣੋ।", "Okay, nothing was booked. Pick any step above to change it."),
}

# Pieces that only make sense in one language (word order differs).
PA_ONLY_PROMPTS = {"frac_sava", "frac_saadhe", "frac_paune"}
EN_ONLY_PROMPTS = {"and_quarter", "and_half", "and_three_quarters"}

LANGS: tuple[str, ...] = ("pa", "en")

STEPS: tuple[str, ...] = ("phone", "village", "acres", "machine", "date")

STEP_TITLES: dict[str, tuple[str, str]] = {
    "phone": ("ਫ਼ੋਨ", "Phone"),
    "village": ("ਪਿੰਡ", "Village"),
    "acres": ("ਏਕੜ", "Acres"),
    "machine": ("ਮਸ਼ੀਨ", "Machine"),
    "date": ("ਤਾਰੀਖ਼", "Date"),
}

# What to type, shown under the mic.
STEP_HINTS: dict[str, tuple[str, str]] = {
    "phone": ("ਮੋਬਾਈਲ ਨੰਬਰ (ਜਿਵੇਂ 9876543210)", "Mobile number (e.g. 9876543210)"),
    "village": ("ਪਿੰਡ ਦਾ ਨਾਂ", "Village name"),
    "acres": ("ਏਕੜ (ਜਿਵੇਂ 5 ਜਾਂ ਸਾਢੇ 3)", "Acres (e.g. 5 or 3.5)"),
    "machine": ("ਮਸ਼ੀਨ ਚੁਣੋ", "Choose a machine"),
    "date": ("ਕਟਾਈ ਦੀ ਤਾਰੀਖ਼", "Harvest date"),
}

# The acreages that get a whole clip of their own (best prosody):
#   every quarter up to 30, every half up to 99.5, every whole number up to 200.
# Anything else is read as a prefix clip + whole-number clip ("ਸਵਾ" + "45 ਏਕੜ").
ACRES_MAX_X100 = 20000
ACRES_MIN_X100 = 25


@dataclass(frozen=True)
class Clip:
    id: str
    text: str


def number_words(n: int) -> str:
    """0..200 as spoken Punjabi."""
    if n < 0 or n > 200:
        raise ValueError(f"number out of range: {n}")
    if n <= 100:
        return NUMBER_WORDS[n][0]
    if n == 200:
        return "ਦੋ ਸੌ"
    return f"ਇੱਕ ਸੌ {NUMBER_WORDS[n - 100][0]}"


def acres_has_own_clip(x100: int) -> bool:
    if x100 < ACRES_MIN_X100 or x100 > ACRES_MAX_X100:
        return False
    if x100 % 25:
        return False
    if x100 <= 3000:
        return True
    if x100 <= 9950 and x100 % 50 == 0:
        return True
    return x100 % 100 == 0


def acres_words(x100: int) -> str:
    """Spoken Punjabi for an acreage that has its own clip (quarter steps)."""
    whole, part = divmod(x100, 100)
    special = {25: "ਚੌਥਾਈ ਏਕੜ", 50: "ਅੱਧਾ ਏਕੜ", 75: "ਪੌਣਾ ਏਕੜ", 125: "ਸਵਾ ਏਕੜ", 150: "ਡੇਢ ਏਕੜ", 250: "ਢਾਈ ਏਕੜ"}
    if x100 in special:
        return special[x100]
    if part == 0:
        return f"{number_words(whole)} ਏਕੜ"
    if part == 25:
        return f"ਸਵਾ {number_words(whole)} ਏਕੜ"
    if part == 50:
        return f"ਸਾਢੇ {number_words(whole)} ਏਕੜ"
    if part == 75:
        return f"ਪੌਣੇ {number_words(whole + 1)} ਏਕੜ"
    raise ValueError(f"acres not on a quarter step: {x100}")


def acres_words_en(x100: int) -> str:
    """Spoken English for an acreage that has its own clip (quarter steps)."""
    whole, part = divmod(x100, 100)
    special = {25: "a quarter acre", 50: "half an acre", 75: "three quarters of an acre", 100: "one acre"}
    if x100 in special:
        return special[x100]
    if part == 0:
        return f"{whole} acres"
    frac = {25: "and a quarter", 50: "and a half", 75: "and three quarter"}[part]
    return f"{whole} {frac} acres"


def acres_clips(x100: int, lang: str = "pa") -> list[str]:
    """Clip ids that read an acreage aloud. Values off the quarter grid use the nearest quarter."""
    q = int(round(x100 / 25.0)) * 25
    q = max(ACRES_MIN_X100, min(ACRES_MAX_X100, q))
    if acres_has_own_clip(q):
        return [f"acres/{q}"]
    whole, part = divmod(q, 100)
    if lang == "en":
        # "45 acres" + "and a quarter"
        tail = {25: "and_quarter", 50: "and_half", 75: "and_three_quarters"}[part]
        return [f"acres/{whole * 100}", f"prompt/{tail}"]
    if part == 25:
        return ["prompt/frac_sava", f"acres/{whole * 100}"]
    if part == 50:
        return ["prompt/frac_saadhe", f"acres/{whole * 100}"]
    # part == 75
    return ["prompt/frac_paune", f"acres/{(whole + 1) * 100}"]


def date_words(month: int, day: int) -> str:
    day_word = "ਪਹਿਲੀ" if day == 1 else number_words(day)
    return f"{day_word} {MONTH_WORDS[month][0]}"


def ordinal_en(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


EN_MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"]
EN_DIGITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def date_words_en(month: int, day: int) -> str:
    return f"{ordinal_en(day)} {EN_MONTHS[month]}"


def date_clip(month: int, day: int) -> str:
    return f"date/{month:02d}-{day:02d}"


def village_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return slug or "village"


def village_clip(name: str) -> str:
    return f"village/{village_slug(name)}"


def village_words(entry: VillageEntry) -> str:
    return entry.name_pa if entry.name_pa.startswith("ਪਿੰਡ") else f"ਪਿੰਡ {entry.name_pa}"


def machine_clip(service_type: str) -> str:
    return f"machine/{service_type}"


def build_clips(villages: list[VillageEntry] | None = None, lang: str = "pa") -> list[Clip]:
    """Every clip the flow can play in one language, in a stable order. Same ids in both languages."""
    if lang not in LANGS:
        raise ValueError(f"unknown language: {lang}")
    en = lang == "en"
    skip = PA_ONLY_PROMPTS if en else EN_ONLY_PROMPTS
    clips: list[Clip] = [Clip(f"prompt/{k}", e if en else pa) for k, (pa, e) in PROMPTS.items() if k not in skip]
    clips += [Clip(f"digit/{d}", EN_DIGITS[d] if en else NUMBER_WORDS[d][0]) for d in range(10)]
    for entry in villages if villages is not None else list(VILLAGES_PA):
        clips.append(Clip(village_clip(entry.name), entry.name if en else village_words(entry)))
    clips += [Clip(machine_clip(m.id), m.name_en if en else m.name_pa) for m in MACHINES]
    clips += [
        Clip(f"acres/{x}", acres_words_en(x) if en else acres_words(x))
        for x in range(ACRES_MIN_X100, ACRES_MAX_X100 + 1, 25)
        if acres_has_own_clip(x)
    ]
    days_in_month = {1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
    for month, days in days_in_month.items():
        for day in range(1, days + 1):
            clips.append(Clip(date_clip(month, day), date_words_en(month, day) if en else date_words(month, day)))
    return clips
