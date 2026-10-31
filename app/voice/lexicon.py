"""Punjabi word lists for the voice booking flow.

Everything the voice engine needs to hear or say lives here: numbers, months,
weekdays, village and machine names, yes/no words and a few festival dates.
The first spelling in each list is the one sent to the voice generator; the
rest are spellings that speech-to-text (or a person typing) may produce.

Pure data. No clock, no database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# ── Numbers ──────────────────────────────────────────────────────────────
# 0..100. First spelling is spoken by the generator.
NUMBER_WORDS: dict[int, list[str]] = {
    0: ["ਜ਼ੀਰੋ", "ਜੀਰੋ", "ਸਿਫ਼ਰ", "ਸਿਫਰ", "ਸੁੰਨ", "zero"],
    1: ["ਇੱਕ", "ਇਕ", "one"],
    2: ["ਦੋ", "two"],
    3: ["ਤਿੰਨ", "ਤਿਨ", "ਤੀਨ", "three"],
    4: ["ਚਾਰ", "four"],
    5: ["ਪੰਜ", "five"],
    6: ["ਛੇ", "ਛੈ", "six"],
    7: ["ਸੱਤ", "ਸਤ", "seven"],
    8: ["ਅੱਠ", "ਅਠ", "eight"],
    9: ["ਨੌਂ", "ਨੌ", "nine"],
    10: ["ਦਸ", "ten"],
    11: ["ਗਿਆਰਾਂ", "ਗਿਆਰਾ", "eleven"],
    12: ["ਬਾਰਾਂ", "ਬਾਰਾ", "twelve"],
    13: ["ਤੇਰਾਂ", "thirteen"],
    14: ["ਚੌਦਾਂ", "ਚੌਦਾ", "fourteen"],
    15: ["ਪੰਦਰਾਂ", "ਪੰਦਰਾ", "fifteen"],
    16: ["ਸੋਲ਼ਾਂ", "ਸੋਲਾਂ", "ਸੋਲਾ", "sixteen"],
    17: ["ਸਤਾਰਾਂ", "ਸਤਾਰਾ", "seventeen"],
    18: ["ਅਠਾਰਾਂ", "ਅਠਾਰਾ", "eighteen"],
    19: ["ਉੱਨੀ", "ਉਨੀ", "nineteen"],
    20: ["ਵੀਹ", "twenty"],
    21: ["ਇੱਕੀ", "ਇਕੀ"],
    22: ["ਬਾਈ"],
    23: ["ਤੇਈ"],
    24: ["ਚੌਵੀ", "ਚੌਬੀ"],
    25: ["ਪੱਚੀ", "ਪਚੀ"],
    26: ["ਛੱਬੀ", "ਛਬੀ"],
    27: ["ਸਤਾਈ"],
    28: ["ਅਠਾਈ"],
    29: ["ਉਨੱਤੀ", "ਉਣੱਤੀ"],
    30: ["ਤੀਹ", "thirty"],
    31: ["ਇਕੱਤੀ"],
    32: ["ਬੱਤੀ"],
    33: ["ਤੇਤੀ"],
    34: ["ਚੌਂਤੀ", "ਚੌਤੀ"],
    35: ["ਪੈਂਤੀ"],
    36: ["ਛੱਤੀ"],
    37: ["ਸੈਂਤੀ"],
    38: ["ਅਠੱਤੀ"],
    39: ["ਉਨਤਾਲੀ"],
    40: ["ਚਾਲੀ", "ਚਾਲ੍ਹੀ", "forty"],
    41: ["ਇਕਤਾਲੀ"],
    42: ["ਬਿਆਲੀ"],
    43: ["ਤਰਤਾਲੀ", "ਤਿਰਤਾਲੀ"],
    44: ["ਚੁਤਾਲੀ"],
    45: ["ਪੰਤਾਲੀ"],
    46: ["ਛਿਆਲੀ"],
    47: ["ਸੰਤਾਲੀ"],
    48: ["ਅਠਤਾਲੀ"],
    49: ["ਉਨੰਜਾ", "ਉਨਿੰਜਾ"],
    50: ["ਪੰਜਾਹ", "fifty"],
    51: ["ਇਕਵੰਜਾ"],
    52: ["ਬਵੰਜਾ"],
    53: ["ਤਰਵੰਜਾ"],
    54: ["ਚਰਵੰਜਾ", "ਚੁਰੰਜਾ"],
    55: ["ਪਚਵੰਜਾ"],
    56: ["ਛਪੰਜਾ"],
    57: ["ਸਤਵੰਜਾ"],
    58: ["ਅਠਵੰਜਾ"],
    59: ["ਉਨਾਹਠ"],
    60: ["ਸੱਠ", "sixty"],
    61: ["ਇਕਾਹਠ"],
    62: ["ਬਾਹਠ"],
    63: ["ਤਰੇਹਠ"],
    64: ["ਚੌਂਹਠ"],
    65: ["ਪੈਂਹਠ"],
    66: ["ਛਿਆਹਠ"],
    67: ["ਸਤਾਹਠ"],
    68: ["ਅਠਾਹਠ"],
    69: ["ਉਨੱਤਰ"],
    70: ["ਸੱਤਰ", "seventy"],
    71: ["ਇਕਹੱਤਰ"],
    72: ["ਬਹੱਤਰ"],
    73: ["ਤਿਹੱਤਰ"],
    74: ["ਚੌਹੱਤਰ"],
    75: ["ਪਚੱਤਰ"],
    76: ["ਛਿਹੱਤਰ"],
    77: ["ਸਤੱਤਰ"],
    78: ["ਅਠੱਤਰ"],
    79: ["ਉਨਾਸੀ"],
    80: ["ਅੱਸੀ", "eighty"],
    81: ["ਇਕਾਸੀ"],
    82: ["ਬਿਆਸੀ"],
    83: ["ਤਿਰਾਸੀ"],
    84: ["ਚੁਰਾਸੀ"],
    85: ["ਪਚਾਸੀ"],
    86: ["ਛਿਆਸੀ"],
    87: ["ਸਤਾਸੀ"],
    88: ["ਅਠਾਸੀ"],
    89: ["ਉਨਾਨਵੇਂ"],
    90: ["ਨੱਬੇ", "ninety"],
    91: ["ਇਕਾਨਵੇਂ"],
    92: ["ਬਾਨਵੇਂ"],
    93: ["ਤਰਾਨਵੇਂ"],
    94: ["ਚੁਰਾਨਵੇਂ"],
    95: ["ਪਚਾਨਵੇਂ"],
    96: ["ਛਿਆਨਵੇਂ"],
    97: ["ਸਤਾਨਵੇਂ"],
    98: ["ਅਠਾਨਵੇਂ"],
    99: ["ਨੜਿੱਨਵੇਂ"],
    100: ["ਸੌ", "hundred"],
}

# Word -> number, built from NUMBER_WORDS (all spellings).
WORD_TO_NUMBER: dict[str, int] = {}
for _n, _words in NUMBER_WORDS.items():
    for _w in _words:
        WORD_TO_NUMBER.setdefault(_w, _n)

# "ਦੋ ਸੌ", "ਇੱਕ ਸੌ ਵੀਹ": the hundreds word.
HUNDRED_WORDS = {"ਸੌ", "hundred"}

# Ordinals, mostly used with dates: "ਪਹਿਲੀ ਨਵੰਬਰ".
ORDINAL_WORDS: dict[str, int] = {
    "ਪਹਿਲੀ": 1, "ਪਹਿਲਾ": 1, "ਦੂਜੀ": 2, "ਦੂਸਰੀ": 2, "ਤੀਜੀ": 3, "ਚੌਥੀ": 4,
    "ਪੰਜਵੀਂ": 5, "ਛੇਵੀਂ": 6, "ਸੱਤਵੀਂ": 7, "ਅੱਠਵੀਂ": 8, "ਨੌਵੀਂ": 9, "ਦਸਵੀਂ": 10,
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
    "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13,
    "fourteenth": 14, "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20, "thirtieth": 30,
}

# English number words for compounds ("twenty one", "one hundred and five").
EN_UNITS: dict[str, int] = {
    "zero": 0, "oh": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
EN_TENS: dict[str, int] = {
    "twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}

# Gurmukhi and Devanagari digits -> ASCII.
DIGIT_TRANSLATE = str.maketrans("੦੧੨੩੪੫੬੭੮੯०१२३४५६७८९", "01234567890123456789")

# Single-digit words that are safe inside a phone number (no 2-digit words).
# "ਨੋ"/"oh" are common ways of saying 0/9 in a number; keep them here only.
PHONE_EXTRA_DIGIT_WORDS: dict[str, int] = {"oh": 0, "o": 0, "ਨੋ": 9, "ਜ਼ੀਰੋ": 0}
DOUBLE_WORDS = {"ਡਬਲ", "double", "ਦੋਹਰਾ"}
TRIPLE_WORDS = {"ਟ੍ਰਿਪਲ", "ਟਰਿਪਲ", "triple", "ਤੀਹਰਾ"}

# ── Fractions and land units (acres) ────────────────────────────────────
# A prefix changes the next number: "ਸਾਢੇ ਪੰਜ" = 5.5, "ਪੌਣੇ ਚਾਰ" = 3.75.
FRACTION_PREFIX: dict[str, float] = {
    "ਸਵਾ": 0.25,
    "ਸਾਢੇ": 0.5, "ਸਾਡੇ": 0.5, "ਸਾਢੇਂ": 0.5,
    "ਪੌਣੇ": -0.25, "ਪੋਣੇ": -0.25,
}
# Words that are a whole quantity by themselves.
FRACTION_ALONE: dict[str, float] = {
    "ਅੱਧਾ": 0.5, "ਅਧਾ": 0.5, "ਅੱਧ": 0.5, "half": 0.5,
    "ਪੌਣਾ": 0.75, "ਪੋਣਾ": 0.75,
    "ਚੌਥਾਈ": 0.25, "ਚੋਥਾਈ": 0.25, "quarter": 0.25,
    "ਡੇਢ": 1.5, "ਡੇਡ": 1.5, "ਡੇਢ਼": 1.5,
    "ਢਾਈ": 2.5, "ਢਾਈਂ": 2.5, "ਡਾਈ": 2.5,
}
# Land units in acres. Punjab: 1 killa = 1 acre = 8 kanal = 160 marla.
LAND_UNITS: dict[str, float] = {
    "ਏਕੜ": 1.0, "ਏਕੜਾਂ": 1.0, "ਐਕੜ": 1.0, "acre": 1.0, "acres": 1.0, "ekad": 1.0, "ekar": 1.0,
    "ਕਿੱਲਾ": 1.0, "ਕਿੱਲੇ": 1.0, "ਕਿੱਲਿਆਂ": 1.0, "ਕਿਲਾ": 1.0, "ਕਿਲੇ": 1.0, "ਕਿੱਲਾਂ": 1.0,
    "killa": 1.0, "kille": 1.0,
    "ਕਨਾਲ": 0.125, "ਕਨਾਲਾਂ": 0.125, "ਕਨਾਲ਼": 0.125, "kanal": 0.125,
    "ਮਰਲਾ": 1 / 160, "ਮਰਲੇ": 1 / 160, "ਮਰਲਿਆਂ": 1 / 160, "marla": 1 / 160,
    "ਹੈਕਟੇਅਰ": 2.4711, "ਹੈਕਟੇਅਰਾਂ": 2.4711, "hectare": 2.4711, "hectares": 2.4711,
}

# ── Dates ────────────────────────────────────────────────────────────────
MONTH_WORDS: dict[int, list[str]] = {
    1: ["ਜਨਵਰੀ", "january", "jan"],
    2: ["ਫ਼ਰਵਰੀ", "ਫਰਵਰੀ", "february", "feb"],
    3: ["ਮਾਰਚ", "march", "mar"],
    4: ["ਅਪ੍ਰੈਲ", "ਅਪਰੈਲ", "april", "apr"],
    5: ["ਮਈ", "may"],
    6: ["ਜੂਨ", "june", "jun"],
    7: ["ਜੁਲਾਈ", "july", "jul"],
    8: ["ਅਗਸਤ", "august", "aug"],
    9: ["ਸਤੰਬਰ", "ਸਿਤੰਬਰ", "ਸਤੰਬਰ", "september", "sep", "sept"],
    10: ["ਅਕਤੂਬਰ", "ਅਕਤੂਬਰ", "october", "oct"],
    11: ["ਨਵੰਬਰ", "ਨਵੰਬਰ", "november", "nov"],
    12: ["ਦਸੰਬਰ", "december", "dec"],
}
WORD_TO_MONTH: dict[str, int] = {w: m for m, ws in MONTH_WORDS.items() for w in ws}

# Monday = 0 (Python weekday()).
WEEKDAY_WORDS: dict[int, list[str]] = {
    0: ["ਸੋਮਵਾਰ", "ਸੋਮਵਾਰੀ", "monday"],
    1: ["ਮੰਗਲਵਾਰ", "tuesday"],
    2: ["ਬੁੱਧਵਾਰ", "ਬੁਧਵਾਰ", "wednesday"],
    3: ["ਵੀਰਵਾਰ", "ਬੀਰਵਾਰ", "thursday"],
    4: ["ਸ਼ੁੱਕਰਵਾਰ", "ਸ਼ੁਕਰਵਾਰ", "ਸੁੱਕਰਵਾਰ", "friday"],
    5: ["ਸ਼ਨੀਵਾਰ", "ਸ਼ਨਿੱਚਰਵਾਰ", "ਸਨਿੱਚਰਵਾਰ", "ਛਨਿੱਚਰਵਾਰ", "saturday"],
    6: ["ਐਤਵਾਰ", "sunday"],
}
WORD_TO_WEEKDAY: dict[str, int] = {w: d for d, ws in WEEKDAY_WORDS.items() for w in ws}

TODAY_WORDS = {"ਅੱਜ", "ਅਜ", "today", "aaj"}
KAL_WORDS = {"ਕੱਲ੍ਹ", "ਕੱਲ", "ਕਲ", "ਕੱਲ੍", "ਕਲ੍ਹ", "kal", "tomorrow", "yesterday"}
# English phrases that are two days away (checked before "tomorrow"/"yesterday").
DAY_AFTER_TOMORROW = ("day after tomorrow", "ਕੱਲ੍ਹ ਤੋਂ ਬਾਅਦ")
DAY_BEFORE_YESTERDAY = ("day before yesterday",)
PARSON_WORDS = {"ਪਰਸੋਂ", "ਪਰਸੋ", "ਪਰਸੂੰ", "parson"}
DAY_WORDS = {"ਦਿਨ", "ਦਿਨਾਂ", "ਦਿਹਾੜੇ", "days", "day"}
WEEK_WORDS = {"ਹਫ਼ਤੇ", "ਹਫਤੇ", "ਹਫ਼ਤਾ", "ਹਫਤਾ", "ਹਫ਼ਤਿਆਂ", "week", "weeks"}
DATE_FILLER = {"ਤਾਰੀਖ਼", "ਤਾਰੀਖ", "ਤਰੀਕ", "ਤਰੀਖ", "ਤਾਰੀਕ", "date", "tarikh", "th", "st", "nd", "rd", "of", "the", "on"}

PAST_WORDS = {
    "ਸੀ", "ਗਈ", "ਗਿਆ", "ਹੋਈ", "ਕੱਟੀ", "ਕੱਟਿਆ", "ਕਟਿਆ", "ਕਟੀ", "ਲਿਆ", "ਪਹਿਲਾਂ",
    "ਪਹਿਲੇ", "ਬੀਤਿਆ", "ਬੀਤੇ", "ਪਿਛਲੇ", "ਪਿਛਲੀ", "ਪਿੱਛੇ", "ago", "last", "yesterday", "did",
    "was", "were", "harvested", "finished", "done", "previous", "before",
}
FUTURE_WORDS = {
    "ਬਾਅਦ", "ਬਾਦ", "ਅਗਲੇ", "ਅਗਲੀ", "ਆਉਣ", "ਆਉਂਦੇ", "ਹੋਣੀ", "ਕਰਨੀ", "ਕੱਟਣੀ",
    "after", "next", "tomorrow", "will", "going", "gonna", "shall", "coming", "upcoming",
}
# Endings of future-tense verbs: ਹੋਵੇਗੀ, ਕੱਟਾਂਗੇ, ਹੋਊਗੀ.
FUTURE_ENDINGS = ("ਗੀ", "ਗਾ", "ਗੇ", "ਊਗੀ")

NOT_YET_PHRASES = [
    "ਪਤਾ ਨਹੀਂ", "ਪਤਾ ਨਹੀ", "ਨਹੀਂ ਪਤਾ", "ਨਹੀ ਪਤਾ", "ਹਾਲੇ ਨਹੀਂ", "ਹਾਲੇ ਨਹੀ", "ਅਜੇ ਨਹੀਂ",
    "ਅਜੇ ਨਹੀ", "ਨਹੀਂ ਕੱਟ", "ਨਹੀਂ ਕਟ", "ਨਹੀਂ ਹੋਈ", "ਪੱਕੀ ਨਹੀਂ", "ਪਤਾ ਨੀ", "ਨੀ ਪਤਾ",
    "not yet", "not cut yet", "don't know", "dont know", "do not know", "unknown", "not harvested",
    "haven't harvested", "have not harvested", "not decided", "no idea", "not sure", "not fixed",
]


@dataclass(frozen=True)
class Festival:
    key: str
    when: date
    words: tuple[str, ...]
    name_pa: str


# Fixed dates for the paddy-harvest season. Add next year's rows each season.
FESTIVALS: tuple[Festival, ...] = (
    Festival("dussehra", date(2026, 10, 20), ("ਦੁਸਹਿਰਾ", "ਦੁਸਹਿਰੇ", "ਦਸਹਿਰਾ", "ਦਸਹਿਰੇ", "dussehra"), "ਦੁਸਹਿਰਾ"),
    Festival("diwali", date(2026, 11, 8), ("ਦੀਵਾਲੀ", "ਦਿਵਾਲੀ", "ਦੀਵਾਲੀਂ", "diwali"), "ਦੀਵਾਲੀ"),
    Festival("gurpurab", date(2026, 11, 24), ("ਗੁਰਪੁਰਬ", "ਗੁਰਪੁਰਬ", "ਗੁਰਪੁਰਬੀ", "gurpurab"), "ਗੁਰਪੁਰਬ"),
)

# ── Yes / no ─────────────────────────────────────────────────────────────
YES_WORDS = {
    "ਹਾਂ", "ਹਾਂਜੀ", "ਹਾਂ ਜੀ", "ਹਾ", "ਹਾਜੀ", "ਹੰਜੀ", "ਠੀਕ", "ਸਹੀ", "ਬਿਲਕੁਲ", "ਪੱਕਾ",
    "ਓਕੇ", "ਜੀ", "ਕਰਦੋ", "ਕਰ ਦਿਓ", "ਕਰ ਦਿਉ", "yes", "ok", "okay", "haan", "haanji", "theek",
    "sahi", "yeah", "yep", "yup", "correct", "right", "sure", "absolutely", "fine", "confirm",
    "confirmed", "go ahead",
}
NO_WORDS = {
    "ਨਹੀਂ", "ਨਹੀ", "ਨਾ", "ਨੀ", "ਗਲਤ", "ਗ਼ਲਤ", "ਦੁਬਾਰਾ", "ਬਦਲੋ", "no", "nahi", "galat",
    "wrong", "nope", "nah", "incorrect", "not", "change", "cancel",
}

# ── Machines ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class MachineEntry:
    id: str
    name_pa: str
    name_en: str
    aliases: tuple[str, ...]


MACHINES: tuple[MachineEntry, ...] = (
    MachineEntry("super_seeder", "ਸੁਪਰ ਸੀਡਰ", "Super Seeder",
                 ("ਸੁਪਰ ਸੀਡਰ", "ਸੁਪਰਸੀਡਰ", "ਸੁਪਰ", "ਸੂਪਰ", "super seeder", "superseeder", "super cedar", "super", "supper seeder")),
    MachineEntry("happy_seeder", "ਹੈਪੀ ਸੀਡਰ", "Happy Seeder",
                 ("ਹੈਪੀ ਸੀਡਰ", "ਹੈਪੀਸੀਡਰ", "ਹੈਪੀ", "ਹੈਪੀਂ", "ਹੈਪੀ ਸੀਡਰ", "happy seeder", "happyseeder", "happy cedar", "happy")),
    MachineEntry("baler", "ਬੇਲਰ", "Baler",
                 ("ਬੇਲਰ", "ਬੇਲਰ", "ਬੇਲਰਾਂ", "ਬੇਲ", "ਗੱਠਾਂ", "ਗੰਢਾਂ", "ਗੱਠੜੀਆਂ", "baler", "bailer", "bales", "bale", "bailey", "straw baler")),
    MachineEntry("mulcher", "ਮਲਚਰ", "Mulcher",
                 ("ਮਲਚਰ", "ਮਲਚਰ", "ਮਲਚ", "ਕੁਤਰ", "ਕੁਤਰਨੀ", "mulcher", "mulch", "mulchar", "mulching")),
)
# Words that mean "a seeder" without saying which one.
SEEDER_ONLY = ("ਸੀਡਰ", "ਬਿਜਾਈ", "seeder", "cedar", "ਬੀਜਣੀ", "ਬੀਜਣਾ", "sowing")

# ── Villages ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class VillageEntry:
    name: str  # exactly as stored in the village table / villages.json
    name_pa: str
    aliases: tuple[str, ...] = field(default_factory=tuple)


# Gurmukhi names for the seeded villages. A village that is missing here still
# works: it is matched by its English spelling and read back as text only.
VILLAGES_PA: tuple[VillageEntry, ...] = (
    VillageEntry("Pind Kalan", "ਪਿੰਡ ਕਲਾਂ"),
    VillageEntry("Bhucho Khurd", "ਭੁੱਚੋ ਖੁਰਦ", ("ਭੁੱਚੋ", "ਭੁਚੋ ਖੁਰਦ")),
    VillageEntry("Rampura Phul", "ਰਾਮਪੁਰਾ ਫੂਲ", ("ਰਾਮਪੁਰਾ", "ਰਾਮਪੁਰਾ ਫੂਲ")),
    VillageEntry("Kot Shamir", "ਕੋਟ ਸ਼ਮੀਰ", ("ਕੋਟ ਸਮੀਰ", "ਕੋਟਸ਼ਮੀਰ")),
    VillageEntry("Maur Mandi", "ਮੌੜ ਮੰਡੀ", ("ਮੌੜ", "ਮੋੜ ਮੰਡੀ")),
    VillageEntry("Sangat Kalan", "ਸੰਗਤ ਕਲਾਂ", ("ਸੰਗਤ",)),
    VillageEntry("Talwandi Sabo", "ਤਲਵੰਡੀ ਸਾਬੋ", ("ਤਲਵੰਡੀ", "ਸਾਬੋ ਕੀ ਤਲਵੰਡੀ")),
    VillageEntry("Goniana Mandi", "ਗੋਨਿਆਣਾ ਮੰਡੀ", ("ਗੋਨਿਆਣਾ", "ਗੋਨਿਆਣਾ ਮੰਡੀ")),
    VillageEntry("Tibbi Far", "ਟਿੱਬੀ", ("ਟਿੱਬੀ ਫ਼ਾਰ", "ਟਿੱਬੀ ਫਾਰ", "ਟਿੱਬੀ")),
)

# Small words people wrap around an answer. Removed before fuzzy matching.
FILLER_WORDS = {
    "ਜੀ", "ਮੇਰਾ", "ਮੇਰੀ", "ਮੇਰੇ", "ਸਾਡਾ", "ਸਾਡੀ", "ਸਾਡੇ", "ਦਾ", "ਦੀ", "ਦੇ", "ਹੈ", "ਹਨ", "ਵਿੱਚ",
    "ਵਿਚ", "ਚ", "ਤੋਂ", "ਨਾਮ", "ਨਾਂ", "ਨਾਓਂ", "ਜੀਓ", "ਭਾਈ", "ਹਾਂ", "ਤਾਂ", "ਇਹ", "ਉਹ",
    "ਖੇਤ", "ਸਾਨੂੰ", "ਮੈਨੂੰ", "ਚਾਹੀਦਾ", "ਚਾਹੀਦੀ", "ਚਾਹੀਦੇ", "ਮਸ਼ੀਨ", "ਵਾਲਾ", "ਵਾਲੀ",
    "my", "is", "the", "village", "ji", "our", "in", "at", "from", "name", "its", "it", "s", "field",
    "farm", "located", "called",
}

GREETING_PHRASES = ["ਸਤ ਸ੍ਰੀ ਅਕਾਲ", "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ", "ਸਤ ਸ਼੍ਰੀ ਅਕਾਲ", "sat sri akal", "namaste", "ਨਮਸਤੇ"]


# ══ Hindi ═══════════════════════════════════════════════════════════════
# Farmers in Punjab often answer in Hindi, or mix it in. Devanagari input is
# turned into Gurmukhi letters first (the two alphabets line up almost letter
# for letter), so every rule above works on it. The Hindi words below are
# written in Devanagari and added to the Gurmukhi lists in that converted form.
# Romanised Hindi ("paanch", "kal", "haan") is added as typed.

_DEVA_SPECIAL = {
    "ँ": "ਂ",  # ँ candrabindu -> ਂ bindi
    "ं": "ਂ",  # ं anusvara -> ਂ bindi
    "ऋ": "ਰਿ",  # ऋ -> ਰਿ
    "ऍ": "ਐ",  # ऍ -> ਐ
    "ऎ": "ਏ",  # ऎ -> ਏ
    "ऑ": "ਔ",  # ऑ -> ਔ
    "ऒ": "ਓ",  # ऒ -> ਓ
    "ऩ": "ਨ",  # ऩ -> ਨ
    "ऱ": "ਰ",  # ऱ -> ਰ
    "ऴ": "ਲ਼",  # ऴ -> ਲ਼
    "ष": "ਸ਼",  # ष -> ਸ਼
    "ृ": "੍ਰ",  # ृ -> ੍ਰ
    "ॄ": "੍ਰ",
    "ॅ": "ੈ",  # ॅ -> ੈ
    "ॆ": "ੇ",  # ॆ -> ੇ
    "ॉ": "ੌ",  # ॉ -> ੌ
    "ॊ": "ੋ",  # ॊ -> ੋ
    "क़": "ਕ",  # क़ -> ਕ
    "ढ़": "ੜ",  # ढ़ -> ੜ
    "य़": "ਯ",  # य़ -> ਯ
    "ॐ": "",  # ॐ
}
_GURU_CODEPOINTS = {
    *range(0x0A01, 0x0A04), *range(0x0A05, 0x0A0B), 0x0A0F, 0x0A10, *range(0x0A13, 0x0A29),
    *range(0x0A2A, 0x0A31), 0x0A32, 0x0A33, 0x0A35, 0x0A36, 0x0A38, 0x0A39, 0x0A3C, *range(0x0A3E, 0x0A43),
    0x0A47, 0x0A48, 0x0A4B, 0x0A4C, 0x0A4D, *range(0x0A59, 0x0A5D), 0x0A5E, *range(0x0A66, 0x0A70),
}


def _build_deva_table() -> dict[int, str]:
    table: dict[int, str] = {}
    for cp in range(0x0900, 0x0980):
        ch = chr(cp)
        if ch in _DEVA_SPECIAL:
            table[cp] = _DEVA_SPECIAL[ch]
        elif cp + 0x100 in _GURU_CODEPOINTS:
            table[cp] = chr(cp + 0x100)
    return table


_DEVA_TO_GURU = _build_deva_table()


def deva_to_guru(text: str) -> str:
    """Write Devanagari (Hindi) text in Gurmukhi letters: 'पाँच एकड़' -> 'ਪਾਂਚ ਏਕੜ'. Other text is unchanged."""
    if not any("ऀ" <= ch <= "ॿ" for ch in text):
        return text
    out = text.translate(_DEVA_TO_GURU)
    return out.replace("ਡ਼", "ੜ").replace("ਢ਼", "ੜ")  # ड़/ढ़ written as letter + nukta


_GURU_SPECIAL = {
    "ੰ": "ं",  # ੰ tippi -> ं
    "ਂ": "ं",  # ਂ bindi -> ं
    "ਁ": "ँ",
    "ਲ਼": "ल",  # ਲ਼ -> ल
    "ਸ਼": "श",  # ਸ਼ -> श
    "ੜ": "ड़",  # ੜ -> ड़
    "ੑ": "",
    "ੵ": "",
}


def guru_to_deva(text: str) -> str:
    """Write Gurmukhi in Devanagari letters for Hindi screens and Hindi voice clips: 'ਤਲਵੰਡੀ ਸਾਬੋ' -> 'तलवंडी साबो'."""
    out: list[str] = []
    # Gurmukhi letters with a nukta are usually stored as letter + nukta (Unicode keeps them decomposed).
    text = text.replace("\u0a38\u0a3c", "\u0a36").replace("\u0a32\u0a3c", "\u0a32")
    chars = list(text)
    i = 0
    while i < len(chars):
        ch = chars[i]
        if ch == "ੱ":  # ੱ addak doubles the next consonant: ਭੁੱਚੋ -> भुच्चो
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            if nxt and "ਕ" <= nxt <= "ਹ":
                out.append(chr(ord(nxt) - 0x100) + "्")
            i += 1
            continue
        if ch in _GURU_SPECIAL:
            out.append(_GURU_SPECIAL[ch])
        elif "਀" <= ch <= "੿":
            out.append(chr(ord(ch) - 0x100))
        else:
            out.append(ch)
        i += 1
    return "".join(out)


# 0..100 in Hindi. The first spelling is what the Hindi voice says.
NUMBER_WORDS_HI: dict[int, list[str]] = {
    0: ["शून्य", "ज़ीरो", "जीरो", "सिफ़र"], 1: ["एक"], 2: ["दो"], 3: ["तीन"], 4: ["चार"], 5: ["पाँच", "पांच"],
    6: ["छह", "छः", "छे"], 7: ["सात"], 8: ["आठ"], 9: ["नौ"], 10: ["दस"], 11: ["ग्यारह"], 12: ["बारह"],
    13: ["तेरह"], 14: ["चौदह"], 15: ["पंद्रह", "पन्द्रह"], 16: ["सोलह"], 17: ["सत्रह"], 18: ["अठारह"],
    19: ["उन्नीस"], 20: ["बीस"], 21: ["इक्कीस"], 22: ["बाईस"], 23: ["तेईस"], 24: ["चौबीस"], 25: ["पच्चीस"],
    26: ["छब्बीस"], 27: ["सत्ताईस"], 28: ["अट्ठाईस"], 29: ["उनतीस"], 30: ["तीस"], 31: ["इकतीस"],
    32: ["बत्तीस"], 33: ["तैंतीस"], 34: ["चौंतीस"], 35: ["पैंतीस"], 36: ["छत्तीस"], 37: ["सैंतीस"],
    38: ["अड़तीस"], 39: ["उनतालीस"], 40: ["चालीस"], 41: ["इकतालीस"], 42: ["बयालीस"], 43: ["तैंतालीस"],
    44: ["चौवालीस", "चवालीस"], 45: ["पैंतालीस"], 46: ["छियालीस"], 47: ["सैंतालीस"], 48: ["अड़तालीस"],
    49: ["उनचास"], 50: ["पचास"], 51: ["इक्यावन"], 52: ["बावन"], 53: ["तिरपन"], 54: ["चौवन"],
    55: ["पचपन"], 56: ["छप्पन"], 57: ["सत्तावन"], 58: ["अट्ठावन"], 59: ["उनसठ"], 60: ["साठ"],
    61: ["इकसठ"], 62: ["बासठ"], 63: ["तिरसठ"], 64: ["चौंसठ"], 65: ["पैंसठ"], 66: ["छियासठ"],
    67: ["सड़सठ"], 68: ["अड़सठ"], 69: ["उनहत्तर"], 70: ["सत्तर"], 71: ["इकहत्तर"], 72: ["बहत्तर"],
    73: ["तिहत्तर"], 74: ["चौहत्तर"], 75: ["पचहत्तर"], 76: ["छिहत्तर"], 77: ["सतहत्तर"], 78: ["अठहत्तर"],
    79: ["उन्यासी"], 80: ["अस्सी"], 81: ["इक्यासी"], 82: ["बयासी"], 83: ["तिरासी"], 84: ["चौरासी"],
    85: ["पचासी"], 86: ["छियासी"], 87: ["सत्तासी"], 88: ["अट्ठासी"], 89: ["नवासी"], 90: ["नब्बे"],
    91: ["इक्यानवे"], 92: ["बानवे"], 93: ["तिरानवे"], 94: ["चौरानवे"], 95: ["पंचानवे"], 96: ["छियानवे"],
    97: ["सत्तानवे"], 98: ["अट्ठानवे"], 99: ["निन्यानवे"], 100: ["सौ"],
}

# Romanised Hindi/Punjabi number words (Indian English speech-to-text and typing).
NUMBER_WORDS_ROMAN: dict[int, list[str]] = {
    0: ["shunya", "sifar"], 1: ["ek", "ikk", "ik"], 2: ["do", "doh"], 3: ["teen", "tin", "tinn"], 4: ["char", "chaar"],
    5: ["paanch", "panch", "paanj", "panj"], 6: ["chhe", "chhah", "che", "chah"], 7: ["saat", "satt", "sat"],
    8: ["aath", "ath", "athh"], 9: ["nau", "nao", "naun"], 10: ["das", "dus"], 11: ["gyarah", "gyara", "giaran"],
    12: ["barah", "bara", "baran"], 13: ["terah", "tera", "teran"], 14: ["chaudah", "chauda", "chaudan"],
    15: ["pandrah", "pandra", "pandran"], 16: ["solah", "sola", "solan"], 17: ["satrah", "satra", "staran"],
    18: ["atharah", "athara", "atharan"], 19: ["unnis", "unni"], 20: ["bees", "bis", "veeh"], 25: ["pachees", "pachchi"],
    30: ["tees", "teeh"], 40: ["chalees", "chali"], 50: ["pachaas", "panjah"], 60: ["saath", "satth"],
    70: ["sattar"], 80: ["assi"], 90: ["nabbe"], 100: ["sau"],
}

for _n, _words in NUMBER_WORDS_HI.items():
    for _w in _words:
        WORD_TO_NUMBER.setdefault(deva_to_guru(_w), _n)
for _n, _words in NUMBER_WORDS_ROMAN.items():
    for _w in _words:
        WORD_TO_NUMBER.setdefault(_w, _n)
HUNDRED_WORDS |= {"sau"}

MONTH_WORDS_HI: dict[int, list[str]] = {
    1: ["जनवरी"], 2: ["फ़रवरी", "फरवरी"], 3: ["मार्च"], 4: ["अप्रैल"], 5: ["मई"], 6: ["जून"], 7: ["जुलाई"],
    8: ["अगस्त"], 9: ["सितंबर", "सितम्बर"], 10: ["अक्टूबर", "अक्तूबर"], 11: ["नवंबर", "नवम्बर"], 12: ["दिसंबर", "दिसम्बर"],
}
WEEKDAY_WORDS_HI: dict[int, list[str]] = {
    0: ["सोमवार"], 1: ["मंगलवार"], 2: ["बुधवार"], 3: ["गुरुवार", "बृहस्पतिवार", "वीरवार"],
    4: ["शुक्रवार"], 5: ["शनिवार"], 6: ["रविवार", "इतवार"],
}
for _m, _words in MONTH_WORDS_HI.items():
    for _w in _words:
        WORD_TO_MONTH.setdefault(deva_to_guru(_w), _m)
for _d, _words in WEEKDAY_WORDS_HI.items():
    for _w in _words:
        WORD_TO_WEEKDAY.setdefault(deva_to_guru(_w), _d)
for _d, _words in {0: ["somvar"], 1: ["mangalvar"], 2: ["budhvar"], 3: ["guruvar", "veervar"], 4: ["shukravar"],
                   5: ["shanivar"], 6: ["ravivar", "itvar", "aitvar"]}.items():
    for _w in _words:
        WORD_TO_WEEKDAY.setdefault(_w, _d)


def _g(*words: str) -> set[str]:
    """Hindi words in their Gurmukhi-letter form (how they look after deva_to_guru)."""
    return {deva_to_guru(w) for w in words}


TODAY_WORDS |= _g("आज") | {"aaj", "aj"}
KAL_WORDS |= _g("कल", "कल्ह") | {"kal", "kall", "kalh"}
PARSON_WORDS |= _g("परसों", "परसो") | {"parso", "parsoon", "parson"}
DAY_WORDS |= _g("दिन", "दिनों") | {"din", "dino"}
WEEK_WORDS |= _g("हफ़्ते", "हफ्ते", "हफ़्ता", "हफ्ता", "सप्ताह") | {"hafte", "hafta"}
DATE_FILLER |= _g("तारीख़", "तारीख", "तारीख़", "को") | {"tareekh", "tarikh", "ko"}
PAST_WORDS |= _g("था", "थी", "थे", "गया", "गई", "गयी", "हो", "हुई", "काटी", "कटी", "काट", "पहले", "पिछले",
                 "पिछली", "बीते", "कर", "ली", "लिया") | {"tha", "thi", "gaya", "gayi", "hui", "kati", "pichhle", "pehle"}
FUTURE_WORDS |= _g("बाद", "अगले", "अगली", "आने", "वाले", "वाली", "होगी", "होगा", "करेंगे", "काटेंगे", "करनी",
                   "काटनी") | {"baad", "agle", "agli", "hogi", "karenge", "katenge"}
NOT_YET_PHRASES += [
    deva_to_guru(p) for p in ("पता नहीं", "नहीं पता", "मालूम नहीं", "अभी नहीं", "अभी तय नहीं", "तय नहीं", "अभी नहीं कटी",
                              "नहीं कटी", "पक्का नहीं")
] + ["pata nahi", "nahi pata", "abhi nahi", "malum nahi", "pakka nahi"]
ORDINAL_WORDS.update({deva_to_guru(w): n for w, n in (
    ("पहली", 1), ("पहला", 1), ("दूसरी", 2), ("तीसरी", 3), ("चौथी", 4), ("पाँचवीं", 5), ("पांचवीं", 5), ("छठी", 6),
    ("सातवीं", 7), ("आठवीं", 8), ("नौवीं", 9), ("दसवीं", 10))})
ORDINAL_WORDS.update({"pehli": 1, "pahli": 1, "doosri": 2, "dusri": 2, "teesri": 3})

FRACTION_PREFIX.update({deva_to_guru("सवा"): 0.25, deva_to_guru("साढ़े"): 0.5, deva_to_guru("साढे"): 0.5,
                        deva_to_guru("पौने"): -0.25, "sava": 0.25, "saade": 0.5, "sadhe": 0.5, "saadhe": 0.5,
                        "paune": -0.25})
FRACTION_ALONE.update({deva_to_guru("आधा"): 0.5, deva_to_guru("पौना"): 0.75, deva_to_guru("चौथाई"): 0.25,
                       deva_to_guru("डेढ़"): 1.5, deva_to_guru("डेढ"): 1.5, deva_to_guru("ढाई"): 2.5,
                       "aadha": 0.5, "adha": 0.5, "dedh": 1.5, "dhai": 2.5, "dhaai": 2.5})
LAND_UNITS.update({deva_to_guru("एकड़"): 1.0, deva_to_guru("एकड"): 1.0, deva_to_guru("एकर"): 1.0,
                   deva_to_guru("किल्ला"): 1.0, deva_to_guru("किल्ले"): 1.0, deva_to_guru("कनाल"): 0.125,
                   deva_to_guru("मरला"): 1 / 160, deva_to_guru("मरले"): 1 / 160, deva_to_guru("हेक्टेयर"): 2.4711,
                   "ekad": 1.0, "ekar": 1.0, "ekkar": 1.0, "acar": 1.0})

YES_WORDS |= _g("हाँ", "हां", "हाँजी", "हांजी", "जी हाँ", "जी हां", "ठीक", "ठीक है", "सही", "बिल्कुल", "बिलकुल", "पक्का",
                "हम्म", "कर दो", "कर दीजिए", "करो") | {"ha", "haa", "han", "haanji", "ji haan", "theek hai", "bilkul",
                                                       "pakka", "kar do"}
NO_WORDS |= _g("नहीं", "नही", "ना", "गलत", "ग़लत", "मत", "बदलो", "दोबारा", "रहने दो") | {"nahin", "nai", "na",
                                                                                     "mat", "badlo", "dobara"}
DOUBLE_WORDS |= _g("डबल") | {"dabal"}
TRIPLE_WORDS |= _g("ट्रिपल") | {"tripal"}
FILLER_WORDS |= _g("मेरा", "मेरी", "मेरे", "हमारा", "हमारी", "हमारे", "का", "की", "के", "है", "हैं", "में", "से",
                   "गांव", "गाँव", "नाम", "खेत", "चाहिए", "मशीन", "वाला", "वाली", "जी", "भाई", "तो", "यह", "वह",
                   "मुझे", "हमें") | {"mera", "meri", "hamara", "ka", "ki", "ke", "hai", "mein", "gaon", "gav",
                                       "naam", "khet", "chahiye", "wala", "wali", "pind"}
GREETING_PHRASES += [deva_to_guru(p) for p in ("नमस्ते", "नमस्कार", "राम राम", "सत श्री अकाल", "सत् श्री अकाल")] + [
    "namaskar", "ram ram"]
SEEDER_ONLY += (deva_to_guru("सीडर"), deva_to_guru("बुवाई"), deva_to_guru("बिजाई"), "buvai", "bijai")

MACHINE_NAMES_HI = {"super_seeder": "सुपर सीडर", "happy_seeder": "हैप्पी सीडर", "baler": "बेलर", "mulcher": "मल्चर"}
_MACHINE_ALIASES_HI = {
    "super_seeder": ("सुपर सीडर", "सुपरसीडर", "सुपर"),
    "happy_seeder": ("हैप्पी सीडर", "हैपी सीडर", "हैप्पी", "हैपी"),
    "baler": ("बेलर", "बेलर मशीन", "गठरी", "गांठ"),
    "mulcher": ("मल्चर", "मलचर", "मल्च"),
}
MACHINES = tuple(
    MachineEntry(m.id, m.name_pa, m.name_en, m.aliases + tuple(deva_to_guru(a) for a in _MACHINE_ALIASES_HI[m.id]))
    for m in MACHINES
)
MONTHS_HI = ["", "जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
WEEKDAYS_HI = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]
