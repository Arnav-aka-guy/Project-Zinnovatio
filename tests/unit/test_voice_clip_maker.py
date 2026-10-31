"""The clip maker: runs offline against a stand-in for edge-tts."""

import json
import sys
import types

from scripts import make_voice_clips as maker


class _FakeCommunicate:
    calls: list[str] = []

    def __init__(self, text, voice, rate="+0%", pitch="+0Hz"):
        self.text = text
        _FakeCommunicate.calls.append(text)

    async def stream(self):
        yield {"type": "audio", "data": b"\xff\xf3" + b"\x00" * 2000}


def _fake_module():
    mod = types.ModuleType("edge_tts")
    mod.Communicate = _FakeCommunicate

    async def list_voices():
        return [{"ShortName": "pa-IN-VaaniNeural", "Locale": "pa-IN", "Gender": "Female"},
                {"ShortName": "pa-IN-OjasNeural", "Locale": "pa-IN", "Gender": "Male"},
                {"ShortName": "hi-IN-SwaraNeural", "Locale": "hi-IN", "Gender": "Female"},
                {"ShortName": "hi-IN-MadhurNeural", "Locale": "hi-IN", "Gender": "Male"},
                {"ShortName": "en-IN-NeerjaExpressiveNeural", "Locale": "en-IN", "Gender": "Female"},
                {"ShortName": "en-IN-NeerjaNeural", "Locale": "en-IN", "Gender": "Female"},
                {"ShortName": "en-IN-PrabhatNeural", "Locale": "en-IN", "Gender": "Male"}]

    mod.list_voices = list_voices
    return mod


def test_makes_clips_and_manifest_then_skips_unchanged(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "edge_tts", _fake_module())
    _FakeCommunicate.calls = []
    code = maker.main(["--out", str(tmp_path), "--only", "prompt/ask_,digit/"])
    assert code == 0
    pa = json.loads((tmp_path / "pa" / "manifest.json").read_text(encoding="utf-8"))
    en = json.loads((tmp_path / "en" / "manifest.json").read_text(encoding="utf-8"))
    hi = json.loads((tmp_path / "hi" / "manifest.json").read_text(encoding="utf-8"))
    assert pa["voice"] == "pa-IN-VaaniNeural" and en["voice"] == "en-IN-NeerjaNeural"
    assert hi["voice"] == "hi-IN-SwaraNeural" and hi["clips"]["digit/7"]["text"] == "सात"
    assert "prompt/ask_phone" in pa["clips"] and "digit/7" in pa["clips"]
    assert (tmp_path / "pa" / "digit" / "7.mp3").exists() and (tmp_path / "en" / "digit" / "7.mp3").exists()
    assert pa["clips"]["digit/7"]["text"] == "ਸੱਤ" and en["clips"]["digit/7"]["text"] == "seven"
    assert len(_FakeCommunicate.calls) == 3 * (6 + 10)  # Punjabi, Hindi and English

    _FakeCommunicate.calls = []
    assert maker.main(["--out", str(tmp_path), "--only", "prompt/ask_,digit/"]) == 0
    assert _FakeCommunicate.calls == []  # nothing changed, nothing remade

    assert maker.main(["--out", str(tmp_path), "--only", "digit/", "--voice", "male", "--lang", "en"]) == 0
    en = json.loads((tmp_path / "en" / "manifest.json").read_text(encoding="utf-8"))
    assert en["voice"] == "en-IN-PrabhatNeural"


def test_village_list_includes_seed_villages():
    names = {v.name for v in maker.village_entries()}
    assert "Talwandi Sabo" in names and "Tibbi Far" in names


def test_dry_run_needs_no_network(capsys):
    assert maker.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "clips ->" in out and "ਸਾਢੇ ਪੰਜ ਏਕੜ" in out

