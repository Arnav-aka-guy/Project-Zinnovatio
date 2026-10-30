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
