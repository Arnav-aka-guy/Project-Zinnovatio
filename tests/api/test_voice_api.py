"""Voice booking routes: script and understand."""

from app import clock


def test_voice_routes_need_the_passcode(client):
    assert client.get("/api/voice/script").status_code == 401
    res = client.post("/api/voice/understand", json={"step": "phone", "texts": ["9876543210"]})
    assert res.status_code == 401


def test_script_lists_the_five_steps(client, auth_headers):
    res = client.get("/api/voice/script", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert [s["id"] for s in data["steps"]] == ["phone", "village", "acres", "machine", "date"]
    assert data["steps"][0]["ask_clip"] == "prompt/ask_phone"
    assert data["today"] == clock.today().isoformat()
    assert "prompt/confirm_q" in data["prompts"]
    assert {m["id"] for m in data["machines"]} == {"super_seeder", "happy_seeder", "baler", "mulcher"}
    assert any(v["name"] == "Talwandi Sabo" and v["name_pa"] == "ਤਲਵੰਡੀ ਸਾਬੋ" for v in data["villages"])


def test_understand_phone(client, auth_headers):
    res = client.post(
        "/api/voice/understand",
        headers=auth_headers,
        json={"step": "phone", "texts": ["ਨੌਂ ਅੱਠ ਸੱਤ ਛੇ ਪੰਜ ਚਾਰ ਤਿੰਨ ਦੋ ਇੱਕ ਜ਼ੀਰੋ"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True and body["value"] == "9876543210"
    assert body["readback"][0]["clip"] == "prompt/rb_phone"


def test_understand_today_uses_server_clock(client, auth_headers):
    res = client.post("/api/voice/understand", headers=auth_headers, json={"step": "date", "texts": ["ਅੱਜ"]})
    assert res.json()["value"] == clock.today().isoformat()


def test_understand_with_context(client, auth_headers):
    res = client.post(
        "/api/voice/understand",
        headers=auth_headers,
        json={"step": "phone", "texts": ["43210"], "context": {"partial_phone": "98765"}},
    )
    assert res.json()["value"] == "9876543210"


def test_understand_rejects_bad_step_and_empty_text(client, auth_headers):
    res = client.post("/api/voice/understand", headers=auth_headers, json={"step": "weather", "texts": ["x"]})
    assert res.status_code == 422 and res.json()["error_code"] == "VALIDATION_ERROR"
    res = client.post("/api/voice/understand", headers=auth_headers, json={"step": "phone", "texts": ["  "]})
    assert res.status_code == 422


def test_failed_answer_is_200_with_a_prompt(client, auth_headers):
    res = client.post("/api/voice/understand", headers=auth_headers, json={"step": "machine", "texts": ["ਸੀਡਰ"]})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False and body["error_code"] == "MACHINE_WHICH_SEEDER"
    assert body["prompt"] == "prompt/machine_which_seeder"


def test_understand_in_english(client, auth_headers):
    res = client.post(
        "/api/voice/understand",
        headers=auth_headers,
        json={"step": "acres", "texts": ["forty five and a quarter acres"], "lang": "en"},
    )
    body = res.json()
    assert body["ok"] is True and body["value"] == 45.25
    assert [r["clip"] for r in body["readback"]] == ["acres/4500", "prompt/and_quarter", "prompt/confirm_q"]


def test_script_lists_both_languages(client, auth_headers):
    langs = client.get("/api/voice/script", headers=auth_headers).json()["languages"]
    assert [(lang["id"], lang["speech"]) for lang in langs] == [("pa", "pa-IN"), ("en", "en-IN")]
