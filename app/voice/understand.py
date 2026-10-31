"""Turn what a farmer said (or typed) into a booking value.

`understand(step, texts, today, villages, context)` is a pure function: no
database, no clock, no network. The route passes in today's date and the
village list. Speech-to-text often returns several guesses; they are tried in
order and the first one that makes sense wins.

Every answer carries `readback`: the clip ids to play so the farmer hears the
value back (in Punjabi, Hindi or English: the clip ids are the same in all three)
and can say yes or no.

Answers are understood in Punjabi, Hindi and English, in any of the three
modes. Hindi written in Devanagari is first turned into Gurmukhi letters
(`deva_to_guru`), so the Punjabi rules and the Hindi word lists in
`lexicon.py` both apply to it.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from difflib import SequenceMatcher
from typing import Any

from app.enums import to_x100
from app.voice import catalog
from app.voice.lexicon import (
    DATE_FILLER,
    DAY_AFTER_TOMORROW,
    DAY_BEFORE_YESTERDAY,
    DAY_WORDS,
    DIGIT_TRANSLATE,
    DOUBLE_WORDS,
    EN_TENS,
    EN_UNITS,
    FESTIVALS,
    FILLER_WORDS,
    FRACTION_ALONE,
    FRACTION_PREFIX,
    FUTURE_ENDINGS,
    FUTURE_WORDS,
    GREETING_PHRASES,
    HUNDRED_WORDS,
    KAL_WORDS,
    LAND_UNITS,
    MACHINE_NAMES_HI,
    MACHINES,
    MONTH_WORDS,
    MONTHS_HI,
    NO_WORDS,
    NOT_YET_PHRASES,
    NUMBER_WORDS,
    ORDINAL_WORDS,
    PARSON_WORDS,
    PAST_WORDS,
    PHONE_EXTRA_DIGIT_WORDS,
    SEEDER_ONLY,
    TODAY_WORDS,
    TRIPLE_WORDS,
    VILLAGES_PA,
    WEEK_WORDS,
    WEEKDAY_WORDS,
    WEEKDAYS_HI,
    WORD_TO_MONTH,
    WORD_TO_NUMBER,
    WORD_TO_WEEKDAY,
    YES_WORDS,
    MachineEntry,
    VillageEntry,
    deva_to_guru,
    guru_to_deva,
)

STEPS = ("phone", "village", "acres", "machine", "date", "confirm")

# Harvest dates further than this from today are refused.
DATE_PAST_LIMIT_DAYS = 60
DATE_FUTURE_LIMIT_DAYS = 90

MONTHS_EN = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAYS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

GAP_WORD = 70      # between digits inside a group
GAP_GROUP = 260    # between the two halves of a phone number
GAP_PHRASE = 160   # between a value and "ਕੀ ਇਹ ਠੀਕ ਹੈ ਜੀ?"
GAP_JOIN = 40      # pieces of one phrase ("ਸਾਢੇ" + "45 ਏਕੜ")


@dataclass
class Understanding:
    step: str
    ok: bool
    heard: str = ""
    value: Any = None
    display_pa: str = ""
    display_en: str = ""
    display_hi: str = ""
    readback: list[dict] = field(default_factory=list)
    prompt: str | None = None
    error_code: str | None = None
    confidence: float = 0.0
    alternatives: list[dict] = field(default_factory=list)
    partial: str | None = None
    correction: "Understanding | None" = None

    def as_dict(self) -> dict:
        return {
            "step": self.step,
            "ok": self.ok,
            "heard": self.heard,
            "value": self.value,
            "display_pa": self.display_pa,
            "display_en": self.display_en,
            "display_hi": self.display_hi or self.display_pa,
            "readback": self.readback,
            "prompt": self.prompt,
            "error_code": self.error_code,
            "confidence": round(self.confidence, 2),
            "alternatives": self.alternatives,
            "partial": self.partial,
            "correction": self.correction.as_dict() if self.correction else None,
        }


def _fail(step: str, heard: str, code: str, prompt: str, **kw: Any) -> Understanding:
    return Understanding(step=step, ok=False, heard=heard, error_code=code, prompt=f"prompt/{prompt}", **kw)


def _items(*clips: str, gap: int = GAP_JOIN) -> list[dict]:
    return [{"clip": c, "gap_ms": gap} for c in clips]


def _with_question(items: list[dict]) -> list[dict]:
    if items:
        items[-1]["gap_ms"] = GAP_PHRASE
    return items + [{"clip": "prompt/confirm_q", "gap_ms": 0}]


# ── Text clean-up ────────────────────────────────────────────────────────
_PUNCT = re.compile(r"[,!?;:\"'()\[\]{}…|_“”‘’।॥*#+=<>~`]")


def normalize(text: str) -> str:
    """Lower-case, ASCII digits, punctuation to spaces, digits split from letters."""
    t = unicodedata.normalize("NFC", deva_to_guru(unicodedata.normalize("NFC", text or "")))
    t = t.translate(DIGIT_TRANSLATE).lower()
    for g in GREETING_PHRASES:
        t = t.replace(g, " ")
    t = re.sub(r"(?<=\d),(?=\d{1,2}\b)", ".", t)  # "5,5" -> "5.5" (decimal comma)
    t = _PUNCT.sub(" ", t)
    t = re.sub(r"(?<!\d)[./-]|[./-](?!\d)", " ", t)  # keep . / - only between digits
    t = re.sub(r"(\d)(?=[^\d\s./-])", r"\1 ", t)
    t = re.sub(r"(?<=[^\d\s./-])(\d)", r" \1", t)
    t = english_numbers(re.sub(r"\s+", " ", t).strip())
    t = re.sub(r"\b(\d+) point (\d+)\b", r"\1.\2", t)  # "five point five" -> 5.5
    return t


def english_numbers(text: str) -> str:
    """'ninety eight seventy six' -> '98 76'; 'one hundred and twenty' -> '120'. Other words untouched."""
    tokens = text.split()
    out: list[str] = []
    i = 0
    n = len(tokens)

    def unit(j: int) -> int | None:
        return EN_UNITS.get(tokens[j]) if j < n and tokens[j] != "oh" else None

    while i < n:
        t = tokens[i]
        start = i
        value: int | None = None
        # [a|one..nine] hundred [and] [rest]
        if (t == "a" or (unit(i) is not None and 1 <= unit(i) <= 9)) and i + 1 < n and tokens[i + 1] == "hundred":
            value = 100 * (1 if t == "a" else unit(i))
            i += 2
            if i < n and tokens[i] == "and":
                i += 1
            rest, used = _en_below_100(tokens, i)
            if used:
                value += rest
                i += used
            elif tokens[i - 1] == "and":
                i -= 1  # "a hundred and a half" keeps its "and"
        elif t == "hundred":
            value = 100
            i += 1
        else:
            rest, used = _en_below_100(tokens, i)
            if used:
                value = rest
                i += used
        if value is None:
            out.append(t)
            i = start + 1
        else:
            out.append(str(value))
    return " ".join(out)


def _en_below_100(tokens: list[str], i: int) -> tuple[int, int]:
    if i >= len(tokens):
        return 0, 0
    t = tokens[i]
    if t in EN_TENS:
        if i + 1 < len(tokens) and tokens[i + 1] in EN_UNITS and 1 <= EN_UNITS[tokens[i + 1]] <= 9 and tokens[i + 1] != "oh":
            return EN_TENS[t] + EN_UNITS[tokens[i + 1]], 2
        return EN_TENS[t], 1
    if t in EN_UNITS and t != "oh":
        return EN_UNITS[t], 1
    return 0, 0


_NUKTA_FOLD = str.maketrans({
    "ਸ਼": "ਸ",  # ਸ਼ -> ਸ
    "ਖ਼": "ਖ",  # ਖ਼ -> ਖ
    "ਗ਼": "ਗ",  # ਗ਼ -> ਗ
    "ਜ਼": "ਜ",  # ਜ਼ -> ਜ
    "ਫ਼": "ਫ",  # ਫ਼ -> ਫ
    "ਲ਼": "ਲ",  # ਲ਼ -> ਲ
    "਼": None,      # nukta
    "ੱ": None,      # addak
    "੍": None,      # virama
})


def fold(text: str) -> str:
    """Loose Gurmukhi form for fuzzy matching: no nukta, no addak, nasal marks kept as one."""
    t = unicodedata.normalize("NFC", text).translate(_NUKTA_FOLD)
    t = t.replace("ਂ", "ੰ")  # bindi -> tippi
    return re.sub(r"\s+", " ", t).strip().lower()


_FOLDED_NUMBERS: dict[str, int] = {}


def number_word(token: str) -> int | None:
    """A number word in any spelling: 'ਪੰਜ', 'पाँच' (as ਪਾਂਚ), 'ਪਂਦ੍ਰਹ', 'paanch'."""
    n = WORD_TO_NUMBER.get(token)
    if n is not None:
        return n
    if not _FOLDED_NUMBERS:
        for w, v in WORD_TO_NUMBER.items():
            _FOLDED_NUMBERS.setdefault(fold(w), v)
    return _FOLDED_NUMBERS.get(fold(token))


_ROMAN = {
    "ਕ": "k", "ਖ": "kh", "ਗ": "g", "ਘ": "gh", "ਙ": "n", "ਚ": "ch", "ਛ": "chh", "ਜ": "j", "ਝ": "jh",
    "ਞ": "n", "ਟ": "t", "ਠ": "th", "ਡ": "d", "ਢ": "dh", "ਣ": "n", "ਤ": "t", "ਥ": "th", "ਦ": "d",
    "ਧ": "dh", "ਨ": "n", "ਪ": "p", "ਫ": "ph", "ਬ": "b", "ਭ": "bh", "ਮ": "m", "ਯ": "y", "ਰ": "r",
    "ਲ": "l", "ਵ": "v", "ੜ": "r", "ਸ": "s", "ਹ": "h", "ੰ": "n", "ਂ": "n",
    "ਅ": "a", "ਆ": "a", "ਇ": "i", "ਈ": "i", "ਉ": "u", "ਊ": "u", "ਏ": "e", "ਐ": "ai", "ਓ": "o", "ਔ": "au",
    "ਾ": "a", "ਿ": "i", "ੀ": "i", "ੁ": "u", "ੂ": "u", "ੇ": "e", "ੈ": "ai", "ੋ": "o", "ੌ": "au",
}


def skeleton(text: str) -> str:
    """Consonant skeleton that is the same for 'Talwandi Sabo' and 'ਤਲਵੰਡੀ ਸਾਬੋ'."""
    t = fold(text)
    out = []
    for ch in t:
        out.append(_ROMAN.get(ch, ch))
    s = "".join(out).lower()
    s = s.replace("w", "v").replace("z", "j").replace("f", "p").replace("q", "k").replace("x", "ks").replace("c", "ch")
    s = re.sub(r"[aeiouyh]", "", s)
    s = re.sub(r"[^a-z ]", "", s)
    s = re.sub(r"(.)\1+", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _windows(tokens: list[str], max_n: int = 4) -> list[str]:
    out = []
    for n in range(1, min(max_n, len(tokens)) + 1):
        for i in range(len(tokens) - n + 1):
            out.append(" ".join(tokens[i:i + n]))
    return out


# ── Numbers ──────────────────────────────────────────────────────────────
def _read_number(tokens: list[str], i: int) -> tuple[float, int] | None:
    """Read a number starting at tokens[i]. Returns (value, tokens used)."""
    t = tokens[i]
    if re.fullmatch(r"\d+(\.\d+)?", t):
        return float(t), 1
    base: float | None = None
    if number_word(t) is not None:
        base = float(number_word(t))
    elif t in FRACTION_ALONE:
        base = FRACTION_ALONE[t]
    if base is None:
        return None
    used = 1
    # "ਦੋ ਸੌ", "ਇੱਕ ਸੌ ਵੀਹ", "ਡੇਢ ਸੌ"
    if base < 100 and i + 1 < len(tokens) and tokens[i + 1] in HUNDRED_WORDS:
        base *= 100
        used = 2
        nxt = number_word(tokens[i + 2]) if i + 2 < len(tokens) else None
        if nxt is not None and nxt < 100:
            base += nxt
            used = 3
    return base, used


# ── Phone ────────────────────────────────────────────────────────────────
def _phone_digits(text: str) -> str:
    tokens = normalize(text).replace("+", " ").split()
    digits = ""
    repeat = 1
    for idx, t in enumerate(tokens):
        # "ਬਾਈ ਜੀ" is a way of addressing someone, not the number 22.
        if t == "ਬਾਈ" and (idx == 0 or (idx + 1 < len(tokens) and tokens[idx + 1] == "ਜੀ")):
            continue
        if t in DOUBLE_WORDS:
            repeat = 2
            continue
        if t in TRIPLE_WORDS:
            repeat = 3
            continue
        chunk = ""
        if re.fullmatch(r"[\d./-]+", t):
            chunk = re.sub(r"\D", "", t)
        elif t in PHONE_EXTRA_DIGIT_WORDS:
            chunk = str(PHONE_EXTRA_DIGIT_WORDS[t])
        elif number_word(t) is not None and number_word(t) < 100:
            n = number_word(t)
            chunk = str(n)  # people often read numbers in pairs: "ਅਠਾਨਵੇਂ" = 98
        if chunk:
            if repeat > 1:
                chunk = chunk[0] * repeat + chunk[1:]
            digits += chunk
            repeat = 1
    return digits


def _phone_from(digits: str) -> str:
    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        return digits[1:]
    return digits


def parse_phone(text: str, context: dict) -> Understanding:
    heard = text
    partial = re.sub(r"\D", "", str(context.get("partial_phone") or ""))
    new = _phone_digits(text)
    if not new:
        return _fail("phone", heard, "NOT_UNDERSTOOD", "phone_short" if partial else "retry_generic", partial=partial or None)
    digits = _phone_from(partial + new) if partial else _phone_from(new)
    if len(digits) > 10:
        return _fail("phone", heard, "PHONE_TOO_LONG", "phone_long")
    if digits[0] not in "6789":
        return _fail("phone", heard, "PHONE_BAD_START", "phone_start")
    if len(digits) < 10:
        # Keep what we have and ask for the rest: farmers often say a number in two goes.
        return _fail("phone", heard, "PHONE_TOO_SHORT", "phone_continue", partial=digits,
                     display_pa=digits, display_en=digits, display_hi=digits)
    readback = [{"clip": "prompt/rb_phone", "gap_ms": 120}]
    for idx, d in enumerate(digits):
        readback.append({"clip": f"digit/{d}", "gap_ms": GAP_GROUP if idx == 4 else GAP_WORD})
    pretty = f"{digits[:5]} {digits[5:]}"
    return Understanding(
        step="phone", ok=True, heard=heard, value=digits, display_pa=pretty, display_en=pretty, display_hi=pretty,
        readback=_with_question(readback), confidence=1.0,
    )


# ── Village ──────────────────────────────────────────────────────────────
def village_entries(names: list[str]) -> list[VillageEntry]:
    """Villages from the database, each with its Gurmukhi name when we have one."""
    by_name = {v.name.lower(): v for v in VILLAGES_PA}
    out: list[VillageEntry] = []
    seen: set[str] = set()
    for n in names:
        key = n.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(by_name.get(key, VillageEntry(n.strip(), "")))
    for v in VILLAGES_PA:
        if v.name.lower() not in seen:
            seen.add(v.name.lower())
            out.append(v)
    return out


def _village_score(entry: VillageEntry, raw: str, tokens: list[str]) -> float:
    if raw == entry.name.lower():
        return 1.0
    pa_forms = [f for f in (entry.name_pa, *entry.aliases) if f]
    folded_raw = fold(raw)
    for f in pa_forms:
        ff = fold(f)
        if ff and re.search(rf"(^|\s){re.escape(ff)}(\s|$)", folded_raw):
            return 0.97 if f == entry.name_pa else 0.93
    en = entry.name.lower()
    if re.search(rf"(^|\s){re.escape(en)}(\s|$)", raw):
        return 0.97
    best = 0.0
    en_skel = skeleton(entry.name)
    for w in _windows(tokens):
        fw = fold(w)
        for f in pa_forms:
            best = max(best, _ratio(fw, fold(f)))
        sw = skeleton(w)
        if len(sw.replace(" ", "")) >= 2:
            best = max(best, _ratio(sw, en_skel) * 0.95)
            for f in pa_forms:
                best = max(best, _ratio(sw, skeleton(f)) * 0.95)
    return best


def village_hi(v: VillageEntry) -> str:
    return guru_to_deva(v.name_pa) if v.name_pa else v.name


def _village_alt(v: VillageEntry) -> dict:
    return {"value": v.name, "display_pa": v.name_pa or v.name, "display_en": v.name, "display_hi": village_hi(v)}


def parse_village(text: str, villages: list[VillageEntry]) -> Understanding:
    heard = text
    raw = normalize(text)
    tokens = [t for t in raw.split() if t not in FILLER_WORDS]
    if not raw or not villages:
        return _fail("village", heard, "NOT_UNDERSTOOD", "retry_generic")
    scored = sorted(((_village_score(v, raw, tokens or raw.split()), v) for v in villages), key=lambda x: -x[0])
    best_score, best = scored[0]
    alts = [_village_alt(v) for s, v in scored[:3] if s >= 0.45]
    if best_score < 0.72:
        return _fail("village", heard, "VILLAGE_NOT_FOUND", "village_unknown", alternatives=alts, confidence=best_score)
    if len(scored) > 1 and scored[1][0] >= best_score - 0.03 and best_score < 0.93:
        return _fail("village", heard, "VILLAGE_AMBIGUOUS", "village_unknown", alternatives=alts[:2], confidence=best_score)
    readback = _with_question(_items(catalog.village_clip(best.name)))
    return Understanding(
        step="village", ok=True, heard=heard, value=best.name, display_pa=best.name_pa or best.name,
        display_en=best.name, display_hi=village_hi(best), readback=readback, confidence=best_score,
        alternatives=[_village_alt(v) for s, v in scored[1:3] if s >= 0.6],
    )


# ── Acres ────────────────────────────────────────────────────────────────
_UNIT_RE = r"(?:acres?|killa|kille|kanals?)"


def _english_fractions(t: str) -> str:
    """'5 and a half' -> '5.5', 'half an acre' -> '0.5 acre', '5 acres and a quarter' -> '5.25 acres'."""
    parts = {"half": 0.5, "quarter": 0.25, "3 quarters": 0.75, "3 quarter": 0.75}

    def add(m: re.Match, frac: float) -> str:
        unit = m.group(2) if m.lastindex and m.lastindex >= 2 and m.group(2) else ""
        return f"{float(m.group(1)) + frac:g} {unit}".strip()

    for word, frac in parts.items():
        w = word.replace(" ", r"\s")
        t = re.sub(rf"\b(\d+(?:\.\d+)?)\s(?:{_UNIT_RE}\s)?and\s(?:a\s)?{w}s?\b(?:\s({_UNIT_RE}))?",
                   lambda m, f=frac: add(m, f), t)
    t = re.sub(r"\b(?:3\squarters?)\s(?:of\s)?(?:an?\s)?acre\b", "0.75 acre", t)
    t = re.sub(r"\bhalf\s(?:of\s)?(?:an?\s)?acre\b", "0.5 acre", t)
    t = re.sub(r"\b(?:a\s)?quarter\s(?:of\s)?(?:an?\s)?acre\b", "0.25 acre", t)
    t = re.sub(r"\b(?:an?|one)\sacre\b", "1 acre", t)
    return t


def _acres_value(text: str) -> float | None:
    tokens = _english_fractions(normalize(text)).split()
    total = 0.0
    pending: float | None = None
    prefix: float | None = None
    found = False
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in FRACTION_PREFIX:
            prefix = FRACTION_PREFIX[t]
            i += 1
            continue
        num = _read_number(tokens, i)
        if num is not None:
            v, used = num
            if prefix is not None:
                v = v + prefix
                prefix = None
            if pending is not None:
                total += pending
            pending = v
            found = True
            i += used
            continue
        if t in LAND_UNITS:
            if pending is None and prefix is not None:
                pending = 1.0 + prefix  # "ਸਵਾ ਏਕੜ" = 1.25
                prefix = None
                found = True
            if pending is not None:
                total += pending * LAND_UNITS[t]
                pending = None
        i += 1
    if pending is not None:
        total += pending
    if not found and prefix is not None:
        total, found = 1.0 + prefix, True
    return round(total, 4) if found else None


def parse_acres(text: str, lang: str = "pa") -> Understanding:
    heard = text
    value = _acres_value(text)
    if value is None:
        return _fail("acres", heard, "NOT_UNDERSTOOD", "acres_unknown")
    x100 = to_x100(value)
    if x100 < catalog.ACRES_MIN_X100:
        return _fail("acres", heard, "ACRES_TOO_SMALL", "acres_range")
    if x100 > catalog.ACRES_MAX_X100:
        return _fail("acres", heard, "ACRES_TOO_LARGE", "acres_range")
    acres = x100 / 100
    shown = f"{acres:g}"
    items = _items(*catalog.acres_clips(x100, lang))
    if x100 % 25:
        items = _items("prompt/about") + items
    return Understanding(
        step="acres", ok=True, heard=heard, value=acres, display_pa=f"{shown} ਏਕੜ", display_hi=f"{shown} एकड़",
        display_en=f"{shown} acre" if acres == 1 else f"{shown} acres", readback=_with_question(items), confidence=0.95,
    )


# ── Machine ──────────────────────────────────────────────────────────────
def _machine_hits(raw: str) -> list[MachineEntry]:
    folded = fold(raw)
    tokens = folded.split()
    hits = []
    for m in MACHINES:
        if raw.strip() == m.id:
            return [m]
        for a in m.aliases:
            fa = fold(a)
            if (" " in fa and fa in folded) or fa in tokens:
                hits.append(m)
                break
    return hits


def parse_machine(text: str) -> Understanding:
    heard = text
    raw = normalize(text)
    hits = _machine_hits(raw)
    if not hits:
        # Fuzzy: "ਸੁਪਰਸੀਡਲ", "hapi sidar"
        best, best_m = 0.0, None
        for w in _windows(raw.split(), 2):
            sw = skeleton(w)
            for m in MACHINES:
                for form in (m.name_en, m.name_pa):
                    r = _ratio(sw, skeleton(form))
                    if r > best:
                        best, best_m = r, m
        if best_m is not None and best >= 0.8:
            hits = [best_m]
    if not hits:
        folded = fold(raw)
        if any(fold(s) in folded for s in SEEDER_ONLY):
            seeders = [m for m in MACHINES if m.id in ("super_seeder", "happy_seeder")]
            return _fail("machine", heard, "MACHINE_WHICH_SEEDER", "machine_which_seeder",
                         alternatives=[_machine_alt(m) for m in seeders])
        return _fail("machine", heard, "NOT_UNDERSTOOD", "machine_unknown",
                     alternatives=[_machine_alt(m) for m in MACHINES])
    unique = list(dict.fromkeys(hits))
    if len(unique) > 1:
        return _fail("machine", heard, "MACHINE_AMBIGUOUS", "machine_unknown",
                     alternatives=[_machine_alt(m) for m in unique])
    m = unique[0]
    return Understanding(
        step="machine", ok=True, heard=heard, value=m.id, display_pa=m.name_pa, display_en=m.name_en,
        display_hi=MACHINE_NAMES_HI[m.id],
        readback=_with_question(_items(catalog.machine_clip(m.id))), confidence=0.95,
    )


def _machine_alt(m: MachineEntry) -> dict:
    return {"value": m.id, "display_pa": m.name_pa, "display_en": m.name_en, "display_hi": MACHINE_NAMES_HI[m.id]}


# ── Date ─────────────────────────────────────────────────────────────────
def _tense(tokens: list[str]) -> str | None:
    past = sum(1 for t in tokens if t in PAST_WORDS)
    future = sum(1 for t in tokens if t in FUTURE_WORDS or (len(t) > 3 and t.endswith(FUTURE_ENDINGS)))
    if past > future:
        return "past"
    if future > past:
        return "future"
    return None


def _number_at(tokens: list[str], i: int) -> int | None:
    if i < 0 or i >= len(tokens):
        return None
    t = tokens[i]
    if re.fullmatch(r"\d{1,3}", t):
        return int(t)
    if t in ORDINAL_WORDS:
        return ORDINAL_WORDS[t]
    return number_word(t)


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _nearest_year(today: date, month: int, day: int, tense: str | None) -> date | None:
    options = [d for d in (_safe_date(today.year + k, month, day) for k in (-1, 0, 1)) if d]
    if not options:
        return None
    if tense == "past":
        past = [d for d in options if d <= today]
        options = past or options
    elif tense == "future":
        fut = [d for d in options if d >= today]
        options = fut or options
    return min(options, key=lambda d: abs((d - today).days))


def _nearest_day_of_month(today: date, day: int, tense: str | None) -> date | None:
    options = []
    for k in (-1, 0, 1):
        m = today.month + k
        y = today.year + (m - 1) // 12
        m = (m - 1) % 12 + 1
        d = _safe_date(y, m, day)
        if d:
            options.append(d)
    if tense == "past":
        options = [d for d in options if d <= today] or options
    elif tense == "future":
        options = [d for d in options if d >= today] or options
    return min(options, key=lambda d: abs((d - today).days)) if options else None


def _offset_days(tokens: list[str]) -> int | None:
    """'2 ਦਿਨ ਬਾਅਦ' -> +2, '3 ਦਿਨ ਪਹਿਲਾਂ' -> -3, 'ਅਗਲੇ ਹਫ਼ਤੇ' -> +7."""
    for i, t in enumerate(tokens):
        unit = 1 if t in DAY_WORDS else 7 if t in WEEK_WORDS else 0
        if not unit:
            continue
        n = _number_at(tokens, i - 1)
        if n is None:
            n = 1 if unit == 7 else None
        if n is None:
            continue
        after = tokens[i + 1:i + 3]
        before = tokens[max(0, i - 3):i]
        sign = 0
        if any(w in ("ਪਹਿਲਾਂ", "ਪਹਿਲੇ", "ago", "ਪਿਛਲੇ", "ਪਿਛਲੀ", "last", "previous", "back") for w in after + before):
            sign = -1
        elif any(w in ("ਬਾਅਦ", "ਬਾਦ", "ਨੂੰ", "ਤੱਕ", "ਚ", "after", "ਅਗਲੇ", "ਅਗਲੀ", "next", "in", "within", "later")
                 for w in after + before):
            sign = 1
        if sign:
            return sign * n * unit
    return None


def _resolve_date(text: str, today: date, context: dict) -> tuple[str, Any, float, list[dict]]:
    """Returns (kind, value, confidence, alternatives). kind: date | not_yet | which_kal | none."""
    raw = normalize(text)
    tokens = raw.split()
    for phrase in NOT_YET_PHRASES:
        if normalize(phrase) in raw:
            return "not_yet", None, 0.95, []

    m = re.search(r"\b(20\d\d)-(\d{1,2})-(\d{1,2})\b", raw)
    if m:
        d = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            return "date", d, 1.0, []

    tense = _tense(tokens)

    # Festival: "ਦੀਵਾਲੀ ਤੋਂ ਦੋ ਦਿਨ ਬਾਅਦ"
    for fest in FESTIVALS:
        if any(fold(w) in fold(raw) for w in fest.words):
            off = _offset_days(tokens)
            if off is None:
                if any(w in tokens for w in ("ਬਾਅਦ", "ਬਾਦ", "after")):
                    off = 1
                elif any(w in tokens for w in ("ਪਹਿਲਾਂ", "ਪਹਿਲੇ", "before")):
                    off = -1
                else:
                    off = 0
            return "date", fest.when + timedelta(days=off), 0.85 if off else 0.95, []

    m = re.search(r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b", raw)
    if m:
        dd, mm = int(m.group(1)), int(m.group(2))
        if m.group(3):
            yy = int(m.group(3))
            yy = yy + 2000 if yy < 100 else yy
            d = _safe_date(yy, mm, dd)
        else:
            d = _nearest_year(today, mm, dd, tense)
        if d:
            return "date", d, 0.95, []

    clean = [t for t in tokens if t not in DATE_FILLER]
    for i, t in enumerate(clean):
        if t in WORD_TO_MONTH:
            month = WORD_TO_MONTH[t]
            day = _number_at(clean, i - 1)
            if day is None or not 1 <= day <= 31:
                day = _number_at(clean, i + 1)
            if day and 1 <= day <= 31:
                d = _nearest_year(today, month, day, tense)
                if d:
                    return "date", d, 0.95, []

    if any(p in raw for p in DAY_AFTER_TOMORROW):
        return "date", today + timedelta(days=2), 0.95, []
    if any(p in raw for p in DAY_BEFORE_YESTERDAY):
        return "date", today - timedelta(days=2), 0.95, []

    off = _offset_days(tokens)
    if off is not None:
        return "date", today + timedelta(days=off), 0.9, []

    if any(t in TODAY_WORDS for t in tokens):
        return "date", today, 1.0, []

    has_kal = any(t in KAL_WORDS for t in tokens) or context.get("pending") == "kal"
    if has_kal:
        if "tomorrow" in tokens or tense == "future":
            return "date", today + timedelta(days=1), 0.95, []
        if "yesterday" in tokens or tense == "past":
            return "date", today - timedelta(days=1), 0.95, []
        alts = [_date_alt(today - timedelta(days=1), today), _date_alt(today + timedelta(days=1), today)]
        return "which_kal", None, 0.5, alts

    if any(t in PARSON_WORDS for t in tokens):
        sign = -1 if tense == "past" else 1
        return "date", today + timedelta(days=2 * sign), 0.85, []

    for t in tokens:
        if t in WORD_TO_WEEKDAY:
            wd = WORD_TO_WEEKDAY[t]
            if tense == "past":
                delta = -((today.weekday() - wd) % 7 or 7)
            else:
                delta = (wd - today.weekday()) % 7
            return "date", today + timedelta(days=delta), 0.9, []

    # A bare day: "15 ਤਾਰੀਖ਼", "ਪੰਦਰਾਂ ਨੂੰ"
    content = [t for t in tokens if t not in DATE_FILLER]
    for i, _t in enumerate(content):
        n = _number_at(content, i)
        if n and 1 <= n <= 31:
            d = _nearest_day_of_month(today, n, tense)
            if d:
                return "date", d, 0.8, []
    return "none", None, 0.0, []


def _date_display(d: date) -> tuple[str, str, str]:
    pa = f"{d.day} {MONTH_WORDS[d.month][0]} {d.year} ({WEEKDAY_WORDS[d.weekday()][0]})"
    en = f"{WEEKDAYS_EN[d.weekday()]} {d.day} {MONTHS_EN[d.month]} {d.year}"
    hi = f"{d.day} {MONTHS_HI[d.month]} {d.year} ({WEEKDAYS_HI[d.weekday()]})"
    return pa, en, hi


def _date_alt(d: date, today: date) -> dict:
    pa, en, hi = _date_display(d)
    label_pa = "ਬੀਤਿਆ ਕੱਲ੍ਹ" if d < today else "ਆਉਣ ਵਾਲਾ ਕੱਲ੍ਹ"
    label_en = "Yesterday" if d < today else "Tomorrow"
    label_hi = "बीता हुआ कल" if d < today else "आने वाला कल"
    return {"value": d.isoformat(), "display_pa": f"{label_pa} · {pa}", "display_en": f"{label_en} · {en}",
            "display_hi": f"{label_hi} · {hi}"}


def date_readback(d: date, today: date) -> list[dict]:
    items: list[dict] = []
    if d == today:
        items += _items("prompt/rel_today", gap=90)
    elif d == today - timedelta(days=1):
        items += _items("prompt/rel_yesterday", gap=90)
    elif d == today + timedelta(days=1):
        items += _items("prompt/rel_tomorrow", gap=90)
    items += _items(catalog.date_clip(d.month, d.day))
    return items


def parse_date(text: str, today: date, context: dict) -> Understanding:
    heard = text
    kind, value, conf, alts = _resolve_date(text, today, context)
    if kind == "not_yet":
        return Understanding(
            step="date", ok=True, heard=heard, value="not_cut_yet", display_pa="ਹਾਲੇ ਪੱਕੀ ਨਹੀਂ",
            display_en="Not fixed yet", display_hi="अभी तय नहीं", readback=_with_question(_items("prompt/date_not_yet")), confidence=conf,
        )
    if kind == "which_kal":
        return _fail("date", heard, "DATE_WHICH_KAL", "date_which_kal", alternatives=alts, confidence=conf)
    if kind == "none":
        return _fail("date", heard, "NOT_UNDERSTOOD", "date_unknown")
    d: date = value
    if d < today - timedelta(days=DATE_PAST_LIMIT_DAYS) or d > today + timedelta(days=DATE_FUTURE_LIMIT_DAYS):
        return _fail("date", heard, "DATE_OUT_OF_RANGE", "date_range")
    pa, en, hi = _date_display(d)
    return Understanding(
        step="date", ok=True, heard=heard, value=d.isoformat(), display_pa=pa, display_en=en, display_hi=hi,
        readback=_with_question(date_readback(d, today)), confidence=conf,
    )


# ── Yes / no ─────────────────────────────────────────────────────────────
def parse_confirm(
    text: str, today: date, villages: list[VillageEntry], context: dict, lang: str = "pa"
) -> Understanding:
    heard = text
    raw = normalize(text)
    tokens = raw.split()
    joined = " " + raw + " "
    no = any(t in NO_WORDS for t in tokens) or any(f" {w} " in joined for w in NO_WORDS if " " in w)
    yes = any(t in YES_WORDS for t in tokens) or any(f" {w} " in joined for w in YES_WORDS if " " in w)
    step = context.get("confirm_step")
    correction = None
    if step in STEPS and step != "confirm" and (no or not yes):
        # "ਨਹੀਂ, 15 ਨਵੰਬਰ" or just the corrected value: offer it straight away.
        attempt = _parse_one(step, text, today, villages, {}, lang)
        if attempt.ok:
            correction = attempt
    if no or (correction is not None and not yes):
        return Understanding(step="confirm", ok=True, heard=heard, value=False, display_pa="ਨਹੀਂ",
                             display_en="No", display_hi="नहीं", confidence=0.95, correction=correction)
    if yes:
        return Understanding(step="confirm", ok=True, heard=heard, value=True, display_pa="ਹਾਂ",
                             display_en="Yes", display_hi="हाँ", confidence=0.95)
    return _fail("confirm", heard, "NOT_UNDERSTOOD", "confirm_unknown")


# ── Entry point ──────────────────────────────────────────────────────────
def _parse_one(
    step: str, text: str, today: date, villages: list[VillageEntry], context: dict, lang: str = "pa"
) -> Understanding:
    if step == "phone":
        return parse_phone(text, context)
    if step == "village":
        return parse_village(text, villages)
    if step == "acres":
        return parse_acres(text, lang)
    if step == "machine":
        return parse_machine(text)
    if step == "date":
        return parse_date(text, today, context)
    if step == "confirm":
        return parse_confirm(text, today, villages, context, lang)
    raise ValueError(f"unknown step: {step}")


def _rank(u: Understanding) -> tuple:
    # ok first, then partial phone with more digits, then confidence.
    return (u.ok, len(u.partial or ""), u.confidence)


def understand(
    step: str,
    texts: list[str],
    today: date,
    villages: list[VillageEntry] | None = None,
    context: dict | None = None,
    lang: str = "pa",
) -> Understanding:
    """Try each speech-to-text guess in order; return the first that works, else the best failure.

    `lang` ("pa", "hi" or "en") only changes how a read-back is built; all three languages are understood either way.
    """
    context = context or {}
    villages = villages if villages is not None else list(VILLAGES_PA)
    cleaned = [t.strip() for t in texts if t and t.strip()]
    if not cleaned:
        return _fail(step, "", "NO_SPEECH", "no_speech")
    results = []
    for t in cleaned:
        u = _parse_one(step, t, today, villages, context, lang)
        if u.ok:
            return u
        results.append(u)
    return max(results, key=_rank)


__all__ = ["Understanding", "understand", "village_entries", "normalize", "skeleton", "NUMBER_WORDS"]
