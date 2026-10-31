"""Google Speech-to-Text and Translation for voice booking (Google is mocked; the key never leaves the server)."""

from __future__ import annotations

import base64
import json
import struct

import httpx
import pytest

from app.voice import google

KEY = "test-google-key-not-real"


def wav(seconds: float = 1.0, rate: int = 16000) -> bytes:
    pcm = b"\x00\x01" * int(rate * seconds)
    return (
        b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
        + b"data" + struct.pack("<I", len(pcm)) + pcm
    )


class FakeGoogle:
    def __init__(self):
        self.calls: list[httpx.Request] = []
        self.speech = {"results": [{"alternatives": [{"transcript": "पाँच एकड़", "confidence": 0.9},
                                                     {"transcript": "पांच एकड़"}], "languageCode": "hi-in"}]}
        self.speech_status = 200
        self.translations: dict[str, str] = {}
        self.translate_status = 200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if request.url.host == "speech.googleapis.com":
            if self.speech_status != 200:
                return httpx.Response(self.speech_status, json={"error": {
                    "message": "Cloud Speech-to-Text API has not been used in project 1 before or it is disabled.",
                    "status": "PERMISSION_DENIED"}})
            return httpx.Response(200, json=self.speech)
        if request.url.host == "translation.googleapis.com":
            if self.translate_status != 200:
                return httpx.Response(self.translate_status, json={"error": {"message": "API key not valid."}})
            q = json.loads(request.content)["q"]
            return httpx.Response(200, json={"data": {"translations": [
                {"translatedText": self.translations.get(t, t), "detectedSourceLanguage": "pa"} for t in q]}})
        return httpx.Response(404)

    def body(self, n: int = -1) -> dict:
        return json.loads(self.calls[n].content)


@pytest.fixture
def fake(monkeypatch):
    f = FakeGoogle()
    monkeypatch.setattr(google, "client_factory", lambda: httpx.Client(transport=httpx.MockTransport(f)))
    google.reset_for_tests()
    yield f
    google.reset_for_tests()


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setenv("VAARI_GOOGLE_API_KEY", KEY)
    monkeypatch.delenv("VAARI_VOICE_SPEECH", raising=False)
    monkeypatch.delenv("VAARI_VOICE_TRANSLATE", raising=False)


def post_audio(client, h, audio: bytes, lang="pa", step="acres"):
    return client.post("/api/voice/transcribe", headers=h, data={"lang": lang, "step": step},
                       files={"audio": ("answer.wav", audio, "audio/wav")})


# ── script ───────────────────────────────────────────────────────────────
def test_script_offers_hindi_and_says_how_speech_works(client, auth_headers, monkeypatch):
    monkeypatch.delenv("VAARI_GOOGLE_API_KEY", raising=False)
    s = client.get("/api/voice/script", headers=auth_headers).json()
    assert [lang["id"] for lang in s["languages"]] == ["pa", "hi", "en"]
    assert s["speech"] == {"provider": "browser", "translate": False}
    assert s["steps"][0]["ask_hi"].startswith("कृपया")
    assert s["prompts"]["prompt/confirm_q"]["hi"] == "क्या यह सही है जी?"
    assert all(v["name_hi"] for v in s["villages"]) and s["machines"][0]["name_hi"] == "सुपर सीडर"


def test_script_uses_google_when_a_key_is_set(client, auth_headers, with_key):
    s = client.get("/api/voice/script", headers=auth_headers).json()
    assert s["speech"] == {"provider": "google", "translate": True}
    assert KEY not in json.dumps(s)


# ── transcribe ───────────────────────────────────────────────────────────
def test_transcribe_sends_all_three_languages_and_hints(client, auth_headers, with_key, fake):
    r = post_audio(client, auth_headers, wav(), lang="pa", step="village")
    assert r.status_code == 200, r.text
    assert r.json() == {"texts": ["पाँच एकड़", "पांच एकड़"], "language": "hi-in", "provider": "google", "error": None}
    call = fake.calls[0]
    assert call.url.path == "/v1p1beta1/speech:recognize" and call.url.params["key"] == KEY
    cfg = fake.body()["config"]
    assert cfg["languageCode"] == "pa-Guru-IN"
    assert cfg["alternativeLanguageCodes"] == ["hi-IN", "en-IN"]
    assert (cfg["encoding"], cfg["sampleRateHertz"], cfg["maxAlternatives"]) == ("LINEAR16", 16000, 5)
    phrases = cfg["speechContexts"][0]["phrases"]
    assert "Talwandi Sabo" in phrases and "ਤਲਵੰਡੀ ਸਾਬੋ" in phrases and "तलवंडी साबो" in phrases
    assert base64.b64decode(fake.body()["audio"]["content"])[:4] == b"RIFF"


def test_hindi_mode_listens_for_hindi_first(client, auth_headers, with_key, fake):
    post_audio(client, auth_headers, wav(), lang="hi", step="phone")
    cfg = fake.body()["config"]
    assert cfg["languageCode"] == "hi-IN" and cfg["alternativeLanguageCodes"] == ["pa-Guru-IN", "en-IN"]
    assert "speechContexts" not in cfg  # no hints for phone numbers


def test_answer_said_in_pieces_is_joined(client, auth_headers, with_key, fake):
    fake.speech = {"results": [
        {"alternatives": [{"transcript": "98765"}, {"transcript": "98764"}]},
        {"alternatives": [{"transcript": "43210"}]},
    ]}
    r = post_audio(client, auth_headers, wav(), step="phone")
    assert r.json()["texts"] == ["98765 43210", "98764 43210"]


def test_silence_is_no_speech_not_an_error(client, auth_headers, with_key, fake):
    fake.speech = {}
    r = post_audio(client, auth_headers, wav())
    assert r.status_code == 200 and r.json()["texts"] == [] and r.json()["error"] == "no_speech"
    tiny = post_audio(client, auth_headers, wav(0.1))
    assert tiny.json()["error"] == "no_speech" and len(fake.calls) == 1  # too short: Google not even asked


def test_disabled_api_falls_back_visibly(client, auth_headers, with_key, fake):
    fake.speech_status = 403
    r = post_audio(client, auth_headers, wav())
    assert r.status_code == 503
    assert r.json()["error_code"] == "VOICE_CLOUD_FAILED" and r.json()["details"]["reason"] == "api_disabled"
    health = client.get("/api/health").json()["voice"]
    assert health["last_speech"]["error"] == "api_disabled" and KEY not in json.dumps(health)


def test_transcribe_without_a_key_says_so(client, auth_headers, monkeypatch):
    monkeypatch.delenv("VAARI_GOOGLE_API_KEY", raising=False)
    r = post_audio(client, auth_headers, wav())
    assert r.status_code == 503 and r.json()["error_code"] == "VOICE_CLOUD_OFF"


def test_transcribe_refuses_other_audio(client, auth_headers, with_key, fake):
    assert post_audio(client, auth_headers, b"not a wav file at all, just bytes" * 3).status_code == 422
    assert post_audio(client, auth_headers, wav(rate=44100)).status_code == 422
    assert fake.calls == []


def test_transcribe_needs_sign_in(client, with_key, fake):
    assert post_audio(client, {}, wav()).status_code == 401


# ── translate fallback in understand ─────────────────────────────────────
def test_translation_rescues_an_answer_the_rules_missed(client, auth_headers, with_key, fake):
    said = "ਵੱਡਾ ਖੇਤ"  # the rules cannot read this; pretend Google's English says the size
    fake.translations[said] = "We need five and a half acres ploughed"
    r = client.post("/api/voice/understand", headers=auth_headers,
                    json={"step": "acres", "texts": [said], "lang": "pa"}).json()
    assert r["ok"] and r["value"] == 5.5 and r["via"] == "translate"
    assert r["heard"] == said and r["translated"] == "We need five and a half acres ploughed"
    call = fake.calls[0]
    assert call.url.host == "translation.googleapis.com" and json.loads(call.content)["target"] == "en"


def test_rules_first_translation_only_when_needed(client, auth_headers, with_key, fake):
    r = client.post("/api/voice/understand", headers=auth_headers,
                    json={"step": "acres", "texts": ["ਸਾਢੇ ਪੰਜ ਏਕੜ"]}).json()
    assert r["ok"] and r["via"] == "rules" and fake.calls == []


def test_phone_numbers_are_never_sent_to_translate(client, auth_headers, with_key, fake):
    r = client.post("/api/voice/understand", headers=auth_headers,
                    json={"step": "phone", "texts": ["ਮੇਰਾ ਨੰਬਰ ਬਾਅਦ ਵਿੱਚ"]}).json()
    assert not r["ok"] and fake.calls == []


def test_translation_failure_keeps_the_rules_answer(client, auth_headers, with_key, fake):
    fake.translate_status = 400
    r = client.post("/api/voice/understand", headers=auth_headers,
                    json={"step": "machine", "texts": ["ਕੋਈ ਵੀ"]}).json()
    assert not r["ok"] and r["via"] == "rules"
    assert client.get("/api/health").json()["voice"]["last_translate"]["error"] == "key_invalid"


def test_no_key_no_translation(client, auth_headers, monkeypatch, fake):
    monkeypatch.delenv("VAARI_GOOGLE_API_KEY", raising=False)
    client.post("/api/voice/understand", headers=auth_headers, json={"step": "machine", "texts": ["ਕੋਈ ਵੀ"]})
    assert fake.calls == []


def test_hindi_understand_via_api(client, auth_headers):
    r = client.post("/api/voice/understand", headers=auth_headers,
                    json={"step": "acres", "texts": ["साढ़े पाँच एकड़"], "lang": "hi"}).json()
    assert r["ok"] and r["value"] == 5.5 and r["display_hi"] == "5.5 एकड़"
