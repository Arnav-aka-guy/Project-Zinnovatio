"""The words of every notification, for farmers (Punjabi first) and for staff.

Every notification is delivered inside Vaari itself (the farmer's page, the
staff bell, and phone/desktop alerts from the Vaari app). Nothing is sent by
SMS or WhatsApp. Farmer texts are short, never blame the farmer, and the slot
message reuses the text in `app/messaging/templates.json`.
"""

from __future__ import annotations

from dataclasses import dataclass

from app import clock
from app.config import settings
from app.enums import from_x100
from app.messaging.render import load_templates

FARMER_TEXT: dict[str, dict[str, str]] = {
    "slot_changed": {
        "pa": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ। ਤੁਹਾਡੀ ਮਸ਼ੀਨ ਦੀ ਵਾਰੀ ਬਦਲ ਗਈ ਹੈ। ",
        "en": "Sat Sri Akal ji. Your machine turn has changed. ",
    },
    "will_miss": {
        "pa": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ। ਮਾਫ਼ ਕਰਨਾ, ਤੁਹਾਡੇ {village} ਵਾਲੇ ਖੇਤ ਲਈ ਹਾਲੇ ਸਮੇਂ ਸਿਰ ਮਸ਼ੀਨ ਖ਼ਾਲੀ ਨਹੀਂ ਹੈ। "
        "{centre_name} ਤੁਹਾਨੂੰ ਜਲਦੀ ਫ਼ੋਨ ਕਰੇਗਾ: {centre_phone}",
        "en": "Sat Sri Akal ji. Sorry, no machine is free in time for your field in {village} yet. "
        "{centre_name} will call you soon: {centre_phone}",
    },
    "cancelled": {
        "pa": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ। ਤੁਹਾਡੇ {village} ਵਾਲੇ ਖੇਤ ਦੀ ਮਸ਼ੀਨ ਬੁਕਿੰਗ ਰੱਦ ਹੋ ਗਈ ਹੈ। ਕੋਈ ਗੱਲ ਹੋਵੇ ਤਾਂ ਫ਼ੋਨ ਕਰੋ: {centre_phone}",
        "en": "Sat Sri Akal ji. The machine booking for your field in {village} is cancelled. "
        "Questions? Call {centre_phone}",
    },
    "job_started": {
        "pa": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ। {machine} ਨੇ ਤੁਹਾਡੇ {village} ਵਾਲੇ ਖੇਤ ਵਿੱਚ ਕੰਮ ਸ਼ੁਰੂ ਕਰ ਦਿੱਤਾ ਹੈ। "
        "ਕੰਮ ਪੂਰਾ ਹੋਣ 'ਤੇ ਡਰਾਈਵਰ ਨੂੰ ਕੋਡ {code} ਦੱਸੋ।",
        "en": "Sat Sri Akal ji. {machine} has started work on your field in {village}. "
        "When it is done, tell the driver code {code}.",
    },
    "job_done": {
        "pa": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ। ਤੁਹਾਡੇ {village} ਵਾਲੇ ਖੇਤ ਦਾ ਕੰਮ ਪੂਰਾ ਹੋ ਗਿਆ ਹੈ। ਧੰਨਵਾਦ ਜੀ। ਰਿਕਾਰਡ ਦੇਖਣ ਲਈ ਛੂਹੋ।",
        "en": "Sat Sri Akal ji. The work on your field in {village} is done. Thank you. Tap to see the record.",
    },
    "not_served": {
        "pa": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ। ਅੱਜ ਤੁਹਾਡੇ {village} ਵਾਲੇ ਖੇਤ ਦਾ ਕੰਮ ਨਹੀਂ ਹੋ ਸਕਿਆ। "
        "{centre_name} ਨਵੀਂ ਵਾਰੀ ਲਈ ਫ਼ੋਨ ਕਰੇਗਾ: {centre_phone}",
        "en": "Sat Sri Akal ji. The work on your field in {village} could not be done today. "
        "{centre_name} will call you with a new turn: {centre_phone}",
    },
}

# Short titles for the farmer's phone alert; the text above is the body.
FARMER_TITLE: dict[str, dict[str, str]] = {
    "slot_scheduled": {"pa": "ਮਸ਼ੀਨ ਦੀ ਵਾਰੀ ਪੱਕੀ: {date}", "en": "Machine booked: {date}"},
    "slot_changed": {"pa": "ਵਾਰੀ ਬਦਲੀ: {date}", "en": "Turn changed: {date}"},
    "will_miss": {"pa": "ਹਾਲੇ ਮਸ਼ੀਨ ਖ਼ਾਲੀ ਨਹੀਂ", "en": "No machine free yet"},
    "cancelled": {"pa": "ਬੁਕਿੰਗ ਰੱਦ", "en": "Booking cancelled"},
    "job_started": {"pa": "ਕੰਮ ਸ਼ੁਰੂ: ਕੋਡ {code}", "en": "Work started: code {code}"},
    "job_done": {"pa": "ਕੰਮ ਪੂਰਾ ਹੋ ਗਿਆ", "en": "Work done"},
    "not_served": {"pa": "ਅੱਜ ਕੰਮ ਨਹੀਂ ਹੋ ਸਕਿਆ", "en": "Work could not be done today"},
}

SERVICE_NAMES = {"super_seeder": "Super Seeder", "happy_seeder": "Happy Seeder", "baler": "Baler", "mulcher": "Mulcher"}


@dataclass
class FarmerContext:
    village: str
    acres: str
    machine: str
    date_pa: str
    date_en: str
    code: str
    centre_name: str
    centre_phone: str

    def as_format(self, lang: str) -> dict[str, str]:
        return {
            "village": self.village,
            "acres": self.acres,
            "machine": self.machine,
            "date": self.date_pa if lang == "pa" else self.date_en,
            "code": self.code,
            "centre_name": self.centre_name,
            "centre_phone": self.centre_phone,
        }


def farmer_context(*, plot, req, slot=None, machine=None) -> FarmerContext:
    return FarmerContext(
        village=plot.village_name if plot else "",
        acres=f"{from_x100(req.acres_x100):g}",
        machine=machine.name if machine else SERVICE_NAMES.get(req.service_type, req.service_type),
        date_pa=clock.fmt_pa(slot.service_date) if slot else "",
        date_en=clock.fmt_en(slot.service_date) if slot else "",
        code=slot.service_code if slot else "",
        centre_name=settings.centre_name,
        centre_phone=settings.centre_phone,
    )


def farmer_text(kind: str, lang: str, ctx: FarmerContext) -> str:
    lang = "pa" if lang == "pa" else "en"
    fmt = ctx.as_format(lang)
    if kind in ("slot_scheduled", "slot_changed"):
        body = load_templates()[lang].format(**fmt)
        if kind == "slot_changed":
            body = (
                FARMER_TEXT["slot_changed"][lang] + body.split("। ", 1)[-1]
                if lang == "pa"
                else (FARMER_TEXT["slot_changed"][lang] + body.split(". ", 1)[-1])
            )
        return body
    return FARMER_TEXT[kind][lang].format(**fmt)


def farmer_title(kind: str, lang: str, ctx: FarmerContext) -> str:
    lang = "pa" if lang == "pa" else "en"
    return FARMER_TITLE[kind][lang].format(**ctx.as_format(lang))


# ── Staff alerts (English, short) ────────────────────────────────────────
def staff_alert(kind: str, **v) -> tuple[str, str]:
    """(title, body) for an alert to operators or officers."""
    if kind == "will_miss":
        return (
            f"VR-{v['request_id']} will miss its deadline",
            f"{v['village']} · {v['acres']} ac · {v['service']}. {v['reason']}".strip(),
        )
    if kind == "not_served":
        return (
            f"VR-{v['request_id']} not served today",
            f"{v['village']} · {v['machine']}: {v['reason']}. Call the farmer and book a new turn.",
        )
    if kind == "needs_review":
        return (
            f"Job VR-{v['request_id']} flagged for review",
            f"{v['village']} · {v['machine']}: {v['flags']}. A person should look; flags never penalise anyone.",
        )
    if kind == "machine_inactive":
        return (f"{v['machine']} marked inactive", "Its jobs were planned again. Check the Will Miss list.")
    if kind == "login_locked":
        return ("Staff account locked", f"'{v['username']}' was locked after repeated wrong passwords.")
    if kind == "farmer_unreachable":
        return (
            f"Tell the farmer: VR-{v['request_id']} turn changed",
            f"{v['village']}: the farmer has no phone with Vaari alerts on. Please call and tell them the new turn.",
        )
    if kind == "test":
        return ("Vaari alerts are on", "This device will get alerts for new problems.")
    raise KeyError(kind)


FLAG_WORDS = {
    "position_mismatch": "position outside the plot",
    "too_fast": "finished faster than a machine can work",
    "exact_duplicate_photo": "photo matches another job",
    "code_missing": "farmer's code not entered",
    "code_wrong": "farmer's code did not match",
}

NOT_SERVED_WORDS = {
    "FIELD_NOT_READY": "field not ready",
    "FARMER_ABSENT": "farmer not there",
    "MACHINE_BROKEN": "machine broke down",
    "WEATHER": "weather",
    "OTHER": "other reason",
}


def driver_alert(kind: str, **v) -> tuple[str, str]:
    if kind == "driver_job_added":
        return (f"New job: {v['village']}", f"{v['date']} · {v['acres']} ac · job #{v['seq']}")
    if kind == "driver_job_removed":
        return (f"Job removed: {v['village']}", f"{v['date']} · {v['acres']} ac is no longer on your list")
    if kind == "driver_day_plan":
        return (f"Today: {v['count']} job{'s' if v['count'] != 1 else ''}", v["summary"])
    raise KeyError(kind)
