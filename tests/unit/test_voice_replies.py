"""Unit tests for voice spoken replies and cache generator (Step V3)."""

from pathlib import Path

from app.voice.replies import REPLIES, get_reply

REQUIRED_KEYS = [
    "greeting",
    "consent",
    "ask_phone",
    "ask_village",
    "ask_acres",
    "ask_machine",
    "ask_harvest_date",
    "did_not_understand",
    "summary_intro",
    "ask_confirm",
    "confirmed_with_date",
    "confirmed_needs_info",
    "no_slot_will_miss",
    "cancelled",
    "will_call_you",
    "service_down",
]


def test_all_required_reply_keys_present():
    for key in REQUIRED_KEYS:
        assert key in REPLIES, f"Missing required voice reply key: {key}"
        assert "pa" in REPLIES[key], f"Missing Punjabi text for key: {key}"
        assert "en" in REPLIES[key], f"Missing English text for key: {key}"
        assert len(REPLIES[key]["pa"].strip()) > 0
        assert len(REPLIES[key]["en"].strip()) > 0


def test_get_reply_structure():
    reply = get_reply("greeting")
    assert reply["key"] == "greeting"
    assert "text_pa" in reply and len(reply["text_pa"]) > 0
    assert "text_en" in reply and len(reply["text_en"]) > 0
    assert reply["audio_url"] == "/api/voice/reply/greeting.wav"


def test_get_reply_unknown_key():
    reply = get_reply("unknown_key_xyz")
    assert reply["key"] == "unknown_key_xyz"
    assert reply["text_pa"] == ""
    assert reply["text_en"] == ""


def test_punjabi_review_tags_present():
    replies_path = Path(__file__).resolve().parent.parent.parent / "app" / "voice" / "replies.py"
    content = replies_path.read_text(encoding="utf-8")
    assert content.count("TODO(punjabi-review): native speaker check") >= len(REQUIRED_KEYS)
