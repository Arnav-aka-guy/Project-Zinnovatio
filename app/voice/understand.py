"""Deterministic Python rules for Punjabi voice understanding (Step V5).

Pure Python rules, regex, and fuzzy matching. No AI language models.
Parses Gurmukhi, English, and mixed transcripts for:
  - 10-digit Indian mobile phone numbers (digits, words, double/triple idioms)
  - Land acres (numbers, fractions like ਢਾਈ, ਡੇਢ, ਸਾਢੇ, ਸਵਾ, ਪੌਣੇ)
  - Machine type canonicalization
  - Harvest / required date resolution (relative terms, weekdays, explicit dates)
  - Village name matching (fuzzy match against known villages)
  - Confirmation intents (Yes/No in Punjabi and English)
"""

import datetime
import difflib
import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.clock import today as get_today
from app.intake.normalize import to_ascii_digits

# --- Digits & Number Words ----------------------------------------------------

DIGIT_WORDS = {
    # Gurmukhi words
    "ਜ਼ੀਰੋ": "0", "ਸਿਫ਼ਰ": "0", "ਸਿਫਰ": "0",
    "ਇੱਕ": "1", "ਇਕ": "1",
    "ਦੋ": "2",
    "ਤਿੰਨ": "3", "ਤਿਨ": "3",
    "ਚਾਰ": "4",
    "ਪੰਜ": "5",
    "ਛੇ": "6", "ਛੀ": "6",
    "ਸੱਤ": "7", "ਸਤ": "7",
    "ਅੱਠ": "8", "ਅਠ": "8",
    "ਨੌਂ": "9", "ਨੌ": "9", "ਨੌੰ": "9",
    # Gurmukhi transliterations of English digits
    "ਵਨ": "1", "ਟੂ": "2", "ਥ੍ਰੀ": "3", "ਥਰੀ": "3", "ਫ਼ੋਰ": "4", "ਫੋਰ": "4",
    "ਫ਼ਾਈਵ": "5", "ਫਾਈਵ": "5", "ਸਿਕਸ": "6", "ਸਿਕ੍ਸ": "6", "ਸੈਵਨ": "7",
    "ਏਟ": "8", "ਨਾਈਨ": "9",
    # English words
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}

# Punjabi numbers 1-20 and tens for acres / dates
NUMBER_WORDS = {
    **DIGIT_WORDS,
    "ਦਸ": 10, "ਗਿਆਰਾਂ": 11, "ਬਾਰਾਂ": 12, "ਤੇਰਾਂ": 13, "ਚੌਦਾਂ": 14,
    "ਪੰਦਰਾਂ": 15, "ਸੋਲ਼ਾਂ": 16, "ਸੋਲਾਂ": 16, "ਸਤਾਰਾਂ": 17, "ਅਠਾਰਾਂ": 18,
    "ਉੱਨੀ": 19, "ਵੀਹ": 20, "ਤੀਹ": 30, "ਚਾਲੀ": 40, "ਪੰਜਾਹ": 50,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30,
}

# Multipliers
DOUBLE_WORDS = ("ਡਬਲ", "double")
TRIPLE_WORDS = ("ਟ੍ਰਿਪਲ", "ਟ੍ਰਿਪਲ਼", "triple")

# Fractions
FRACTION_WORDS = {
    "ਡੇਢ": 1.5,
    "ਢਾਈ": 2.5,
    "ਅੱਧਾ": 0.5,
    "half": 0.5,
}

# --- Canonical Machines -------------------------------------------------------

CANONICAL_MACHINES = {
    "super seeder": "Super Seeder",
    "superseeder": "Super Seeder",
    "ਸੁਪਰ ਸੀਡਰ": "Super Seeder",
    "ਸੁਪਰਸੀਡਰ": "Super Seeder",
    "ਸੀਡਰ": "Super Seeder",
    "happy seeder": "Happy Seeder",
    "happyseeder": "Happy Seeder",
    "ਹੈਪੀ ਸੀਡਰ": "Happy Seeder",
    "ਹੈਪੀਸੀਡਰ": "Happy Seeder",
    "zero till drill": "Zero Till Drill",
    "zero drill": "Zero Till Drill",
    "ਜ਼ੀਰੋ ਡਰਿੱਲ": "Zero Till Drill",
    "ਜ਼ੀਰੋ ਟਰਿੱਲ": "Zero Till Drill",
    "mulcher": "Mulcher",
    "ਮਲਚਰ": "Mulcher",
    "rotavator": "Rotavator",
    "ਰੋਟਾਵੇਟਰ": "Rotavator",
    "baler": "Baler",
    "ਬੇਲਰ": "Baler",
}

# --- Weekdays & Relative Dates ------------------------------------------------

WEEKDAYS = {
    "ਸੋਮਵਾਰ": 0, "monday": 0,
    "ਮੰਗਲਵਾਰ": 1, "tuesday": 1,
    "ਬੁੱਧਵਾਰ": 2, "ਬੁਧਵਾਰ": 2, "wednesday": 2,
    "ਵੀਰਵਾਰ": 3, "thursday": 3,
    "ਸ਼ੁੱਕਰਵਾਰ": 4, "ਸ਼ੁਕਰਵਾਰ": 4, "friday": 4,
    "ਸ਼ਨਿੱਚਰਵਾਰ": 5, "ਸ਼ਨੀਵਾਰ": 5, "saturday": 5,
    "ਐਤਵਾਰ": 6, "sunday": 6,
}

MONTH_MAP = {
    "ਜਨਵਰੀ": 1, "january": 1, "jan": 1,
    "ਫ਼ਰਵਰੀ": 2, "ਫਰਵਰੀ": 2, "february": 2, "feb": 2,
    "ਮਾਰਚ": 3, "march": 3, "mar": 3,
    "ਅਪ੍ਰੈਲ": 4, "april": 4, "apr": 4,
    "ਮਈ": 5, "may": 5,
    "ਜੂਨ": 6, "june": 6, "jun": 6,
    "ਜੁਲਾਈ": 7, "july": 7, "jul": 7,
    "ਅਗਸਤ": 8, "august": 8, "aug": 8,
    "ਸਤੰਬਰ": 9, "september": 9, "sep": 9,
    "ਅਕਤੂਬਰ": 10, "october": 10, "oct": 10,
    "ਨਵੰਬਰ": 11, "november": 11, "nov": 11,
    "ਦਸੰਬਰ": 12, "december": 12, "dec": 12,
}

# --- Confirmation Words -------------------------------------------------------

YES_WORDS = {
    "ਹਾਂ", "ਹਾਂਜੀ", "ਹਾਂ ਜੀ", "ਸਹੀ", "ਸਹੀ ਹੈ", "ਬਿਲਕੁਲ", "ਆਹੋ", "ਠੀਕ", "ਠੀਕ ਹੈ",
    "yes", "haan", "haanjee", "correct", "theek hai", "yep", "sure", "ok",
}

NO_WORDS = {
    "ਨਹੀਂ", "ਨਹੀ", "ਨਾ", "ਨਹੀਂ ਜੀ", "ਗ਼ਲਤ", "ਗਲਤ", "ਰੱਦ", "ਰੱਦ ਕਰੋ", "ਕੈਂਸਲ", "ਕੈਂਸਲ ਕਰੋ", "ਬੰਦ ਕਰੋ",
    "no", "nahin", "wrong", "cancel", "nope", "not correct",
}


@dataclass
class VoiceUnderstandingResult:
    phone: Optional[str] = None
    village: Optional[str] = None
    acres: Optional[float] = None
    machine: Optional[str] = None
    harvest_date: Optional[str] = None
    confirmation: Optional[bool] = None  # True (yes), False (no), None (unclear)
    confidence: str = "low"  # "high" | "low"
    missing_fields: List[str] = field(default_factory=list)
    raw_text: str = ""


# --- Extractor Functions ------------------------------------------------------

VILLAGE_CANONICAL = {
    "rampur": "Rampur", "ਰਾਮਪੁਰ": "Rampur",
    "nabha": "Nabha", "ਨਾਭਾ": "Nabha",
    "bhadson": "Bhadson", "ਭਾਦਸੋਂ": "Bhadson",
    "amloh": "Amloh", "ਅਮਲੋਹ": "Amloh",
    "channo": "Channo", "ਛੰਨੋਂ": "Channo",
    "bhunerheri": "Bhunerheri", "ਭੁਨਰਹੇੜੀ": "Bhunerheri",
    "rajpura": "Rajpura", "ਰਾਜਪੁਰਾ": "Rajpura",
    "samana": "Samana", "ਸਮਾਣਾ": "Samana",
    "patiala": "Patiala", "ਪਟਿਆਲਾ": "Patiala",
    "dhablan": "Dhablan", "ਢਾਬਲਾਂ": "Dhablan",
    "kila raipur": "Kila Raipur", "ਕਿਲਾ ਰਾਏਪੁਰ": "Kila Raipur", "ਕਿਲ੍ਹਾ ਰਾਏਪੁਰ": "Kila Raipur",
    "dhandra": "Dhandra", "ਧਾਂਦਰਾਂ": "Dhandra", "ਧਾਂਦਰਾ": "Dhandra",
    "mansuran": "Mansuran", "ਮਨਸੂਰਾਂ": "Mansuran", "ਮਨਸੂਰਾ": "Mansuran",
    "jodhan": "Jodhan", "ਜੋਧਾਂ": "Jodhan", "ਜੋਧਾ": "Jodhan",
    "pind kalan": "Pind Kalan", "ਪਿੰਡ ਕਲਾਂ": "Pind Kalan",
    "bhucho khurd": "Bhucho Khurd", "ਭੁੱਚੋ ਖੁਰਦ": "Bhucho Khurd",
    "rampura phul": "Rampura Phul", "ਰਾਮਪੁਰਾ ਫੂਲ": "Rampura Phul",
    "kot shamir": "Kot Shamir", "ਕੋਟ ਸ਼ਮੀਰ": "Kot Shamir",
    "maur mandi": "Maur Mandi", "ਮੌੜ ਮੰਡੀ": "Maur Mandi",
    "sangat kalan": "Sangat Kalan", "ਸੰਗਤ ਕਲਾਂ": "Sangat Kalan",
    "talwandi sabo": "Talwandi Sabo", "ਤਲਵੰਡੀ ਸਾਬੋ": "Talwandi Sabo",
    "goniana mandi": "Goniana Mandi", "ਗੋਨਿਆਣਾ ਮੰਡੀ": "Goniana Mandi",
    "tibbi far": "Tibbi Far", "ਟਿੱਬੀ ਫ਼ਾਰ": "Tibbi Far",
}


def extract_phone(text: str) -> Optional[str]:
    """Extract a 10-digit Indian mobile number from words, digits, and idioms."""
    tokens = text.lower().replace(",", " ").replace("-", " ").split()
    digits: list[str] = []

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        # Check for double / triple prefix
        multiplier = 1
        if tok in DOUBLE_WORDS and i + 1 < len(tokens):
            multiplier = 2
            i += 1
            tok = tokens[i]
        elif tok in TRIPLE_WORDS and i + 1 < len(tokens):
            multiplier = 3
            i += 1
            tok = tokens[i]

        # Translate word or direct digits
        norm_tok = to_ascii_digits(tok)
        if norm_tok in DIGIT_WORDS:
            digit = DIGIT_WORDS[norm_tok]
            digits.extend([digit] * multiplier)
        elif norm_tok.isdigit():
            if multiplier > 1 and len(norm_tok) == 1:
                digits.extend([norm_tok] * multiplier)
            else:
                digits.append(norm_tok)
        i += 1

    combined = "".join(digits)

    # 1. First check if prefixed with +91 or 91 (12 digits)
    m12 = re.search(r"(?:91|\+91)([6-9]\d{9})", combined)
    if m12:
        return m12.group(1)

    # 2. Check if prefixed with 0 (11 digits)
    m11 = re.search(r"0([6-9]\d{9})", combined)
    if m11:
        return m11.group(1)

    # 3. Check for exact 10 digits starting with 6, 7, 8, or 9
    for match in re.finditer(r"[6-9]\d{9}", combined):
        return match.group(0)

    return None


def extract_acres(text: str) -> Optional[float]:
    """Extract acres supporting fractions (ਢਾਈ=2.5, ਡੇਢ=1.5, ਸਾਢੇ=X+0.5, ਸਵਾ=X+0.25, ਪੌਣੇ=X-0.25).

    When multiple values are present (e.g. self-correction), returns the last mentioned value.
    Prioritizes explicit acre mentions ('5 ਏਕੜ', 'ਢਾਈ ਏਕੜ') over unadorned digits (e.g. dates).
    """
    clean = to_ascii_digits(text.lower())
    clean = clean.replace("ਕਿੱਲੇ", "ਏਕੜ").replace("ਕਿਲੇ", "ਏਕੜ").replace("acres", "ਏਕੜ").replace("acre", "ਏਕੜ")
    tokens = clean.split()

    explicit_candidates: list[tuple[int, float]] = []
    fallback_candidates: list[tuple[int, float]] = []
    compound_consumed = set()

    # 1. Compound fractions: ਸਾਢੇ (X + 0.5), ਸਵਾ (X + 0.25), ਪੌਣੇ (X - 0.25)
    for i, tok in enumerate(tokens):
        if tok in ("ਸਾਢੇ", "saadhe") and i + 1 < len(tokens):
            base = _parse_number_token(tokens[i + 1])
            if base is not None:
                val = base + 0.5
                if 0.5 <= val <= 500.0:
                    compound_consumed.add(i)
                    compound_consumed.add(i + 1)
                    has_unit = (i + 2 < len(tokens) and tokens[i + 2] == "ਏਕੜ") or (i > 0 and tokens[i - 1] == "ਏਕੜ")
                    if has_unit:
                        explicit_candidates.append((i, val))
                    else:
                        fallback_candidates.append((i, val))
        elif tok in ("ਸਵਾ", "sawa") and i + 1 < len(tokens):
            base = _parse_number_token(tokens[i + 1])
            if base is not None:
                val = base + 0.25
                if 0.5 <= val <= 500.0:
                    compound_consumed.add(i)
                    compound_consumed.add(i + 1)
                    has_unit = (i + 2 < len(tokens) and tokens[i + 2] == "ਏਕੜ") or (i > 0 and tokens[i - 1] == "ਏਕੜ")
                    if has_unit:
                        explicit_candidates.append((i, val))
                    else:
                        fallback_candidates.append((i, val))
        elif tok in ("ਪੌਣੇ", "paune") and i + 1 < len(tokens):
            base = _parse_number_token(tokens[i + 1])
            if base is not None:
                val = base - 0.25
                if 0.5 <= val <= 500.0:
                    compound_consumed.add(i)
                    compound_consumed.add(i + 1)
                    has_unit = (i + 2 < len(tokens) and tokens[i + 2] == "ਏਕੜ") or (i > 0 and tokens[i - 1] == "ਏਕੜ")
                    if has_unit:
                        explicit_candidates.append((i, val))
                    else:
                        fallback_candidates.append((i, val))

    # 2. Standalone fractions and single number words/digits
    date_words = {"ਤਾਰੀਖ਼", "ਤਾਰੀਖ", "tareekh", "date"}
    for i, tok in enumerate(tokens):
        if i in compound_consumed:
            continue
        has_unit = (i + 1 < len(tokens) and tokens[i + 1] == "ਏਕੜ") or (i > 0 and tokens[i - 1] == "ਏਕੜ")
        followed_by_date = (i + 1 < len(tokens) and (tokens[i + 1] in MONTH_MAP or tokens[i + 1] in date_words))

        if tok in FRACTION_WORDS:
            val = FRACTION_WORDS[tok]
            if 0.5 <= val <= 500.0:
                if has_unit:
                    explicit_candidates.append((i, val))
                elif not followed_by_date:
                    fallback_candidates.append((i, val))
                continue

        val = _parse_number_token(tok)
        if val is not None and 0.5 <= float(val) <= 500.0:
            if has_unit:
                explicit_candidates.append((i, float(val)))
            elif not followed_by_date:
                fallback_candidates.append((i, float(val)))

    if explicit_candidates:
        explicit_candidates.sort(key=lambda c: c[0])
        return explicit_candidates[-1][1]

    if fallback_candidates:
        fallback_candidates.sort(key=lambda c: c[0])
        return fallback_candidates[-1][1]

    return None


def _parse_number_token(tok: str) -> Optional[float]:
    """Parse a single token into a numeric value (from digit or word)."""
    norm = to_ascii_digits(tok)
    if norm.isdigit() or re.match(r"^\d+\.\d+$", norm):
        return float(norm)
    if tok in NUMBER_WORDS:
        v = NUMBER_WORDS[tok]
        return float(v)
    return None


def extract_machine(text: str) -> Optional[str]:
    """Extract and canonicalize agricultural machine name."""
    s = text.lower()
    for phrase, canonical in sorted(CANONICAL_MACHINES.items(), key=lambda kv: len(kv[0]), reverse=True):
        if phrase in s:
            return canonical
    return None


def extract_date(text: str, base_date: Optional[datetime.date] = None) -> Optional[str]:
    """Extract harvest or required date, returning YYYY-MM-DD.

    Supports:
      - 'ਅੱਜ' (today)
      - 'ਕੱਲ੍ਹ' (tomorrow)
      - 'ਪਰਸੋਂ' (day after tomorrow)
      - Weekdays ('ਸੋਮਵਾਰ', etc.)
      - Explicit dates ('੫ ਨਵੰਬਰ', '5 november', '10 ਤਾਰੀਖ਼')
    """
    if base_date is None:
        base_date = get_today()

    s = to_ascii_digits(text.lower())

    # Relative days
    if "ਅੱਜ" in s or "today" in s:
        return base_date.strftime("%Y-%m-%d")
    if "ਕੱਲ੍ਹ" in s or "ਕੱਲ" in s or "tomorrow" in s:
        return (base_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    if "ਪਰਸੋਂ" in s or "day after tomorrow" in s:
        return (base_date + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
    if "ਨਰਸੋਂ" in s:
        return (base_date + datetime.timedelta(days=3)).strftime("%Y-%m-%d")

    # Weekdays
    for day_word, target_weekday in WEEKDAYS.items():
        if day_word in s:
            days_ahead = (target_weekday - base_date.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7
            target_date = base_date + datetime.timedelta(days=days_ahead)
            return target_date.strftime("%Y-%m-%d")

    # Explicit day + month: '5 ਨਵੰਬਰ', '12 november'
    for month_word, month_num in MONTH_MAP.items():
        pattern = rf"(\d{{1,2}})\s*(?:th|st|nd|rd)?\s*{re.escape(month_word)}"
        m = re.search(pattern, s)
        if not m:
            pattern2 = rf"{re.escape(month_word)}\s*(\d{{1,2}})"
            m = re.search(pattern2, s)
        if m:
            day_num = int(m.group(1))
            year = base_date.year
            # If the month has already passed in the current year, use next year
            if month_num < base_date.month or (month_num == base_date.month and day_num < base_date.day):
                year += 1
            try:
                resolved = datetime.date(year, month_num, day_num)
                return resolved.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Explicit day with 'ਤਾਰੀਖ਼': '੫ ਤਾਰੀਖ਼', '5 tareekh'
    m_day = re.search(r"(\d{1,2})\s*(?:ਤਾਰੀਖ਼|ਤਾਰੀਖ|tareekh|date)", s)
    if m_day:
        day_num = int(m_day.group(1))
        month = base_date.month
        year = base_date.year
        if day_num < base_date.day:
            month += 1
            if month > 12:
                month = 1
                year += 1
        try:
            resolved = datetime.date(year, month, day_num)
            return resolved.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


def extract_village(text: str, known_villages: Optional[List[str]] = None) -> Optional[str]:
    """Match village name against a list of known villages using difflib fuzzy matching."""
    s = text.strip()

    # 1. Exact match against canonical dict (Punjabi or English)
    for name, canonical in sorted(VILLAGE_CANONICAL.items(), key=lambda kv: len(kv[0]), reverse=True):
        if name in s.lower() or name in s:
            return canonical

    # 2. Match against passed known_villages if any
    if known_villages:
        for v in known_villages:
            if v.lower() in s.lower():
                return VILLAGE_CANONICAL.get(v.lower(), v)

    # 3. Fuzzy match token by token
    tokens = s.split()
    candidates = list(VILLAGE_CANONICAL.keys())
    for tok in tokens:
        matches = difflib.get_close_matches(tok.lower(), candidates, n=1, cutoff=0.7)
        if matches:
            return VILLAGE_CANONICAL[matches[0]]

    return None


def extract_confirmation(text: str) -> Optional[bool]:
    """Extract Yes/No confirmation intent."""
    clean = text.lower().strip()
    words = set(re.findall(r"[\w']+", clean))

    # Check for direct phrase match
    for phrase in sorted(YES_WORDS, key=len, reverse=True):
        if phrase in clean:
            return True
    for phrase in sorted(NO_WORDS, key=len, reverse=True):
        if phrase in clean:
            return False

    # Check tokens
    if words & YES_WORDS:
        return True
    if words & NO_WORDS:
        return False

    return None


# --- Combined Understanding Orchestrator --------------------------------------

def understand_voice_turn(
    text: str,
    expected_field: Optional[str] = None,
    base_date: Optional[datetime.date] = None,
    known_villages: Optional[List[str]] = None,
) -> VoiceUnderstandingResult:
    """Analyze a spoken turn and extract booking fields and confirmation."""
    phone = extract_phone(text)
    acres = extract_acres(text)
    machine = extract_machine(text)
    date_val = extract_date(text, base_date=base_date)
    village = extract_village(text, known_villages=known_villages)
    conf = extract_confirmation(text)

    # Determine confidence:
    # If the expected field was specifically requested and extracted, confidence is high.
    confidence = "low"
    if expected_field == "phone" and phone is not None:
        confidence = "high"
    elif expected_field == "acres" and acres is not None:
        confidence = "high"
    elif expected_field == "machine" and machine is not None:
        confidence = "high"
    elif expected_field == "harvest_date" and date_val is not None:
        confidence = "high"
    elif expected_field == "village" and village is not None:
        confidence = "high"
    elif expected_field == "confirm" and conf is not None:
        confidence = "high"
    elif any([phone, acres, machine, date_val, village, conf is not None]):
        confidence = "high"

    # Identify missing fields
    missing: list[str] = []
    if phone is None:
        missing.append("phone")
    if village is None:
        missing.append("village")
    if acres is None:
        missing.append("acres")
    if machine is None:
        missing.append("machine")
    if date_val is None:
        missing.append("harvest_date")

    return VoiceUnderstandingResult(
        phone=phone,
        village=village,
        acres=acres,
        machine=machine,
        harvest_date=date_val,
        confirmation=conf,
        confidence=confidence,
        missing_fields=missing,
        raw_text=text,
    )
