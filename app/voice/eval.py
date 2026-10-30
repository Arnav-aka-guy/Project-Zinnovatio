"""Evaluation runner for Vaari Punjabi voice understanding (Step V8).

Executes: `python tasks.py voice-eval` or `python -m app.voice.eval`.

Evaluates 5 realistic farmer dialogues from examples/voice/SCRIPT.md against
the expected outputs in examples/voice/expected/*.json.
Tests deterministic rule-based extraction accuracy across:
  1. Super Seeder standard happy path
  2. Happy Seeder multi-field turn and explicit date
  3. Noisy speech retry and in-sentence acres correction
  4. Read-back summary date revision
  5. Voluntary cancellation

Optionally probes the local voice microservice at http://127.0.0.1:8100 if running.
Generates / updates docs/VOICE_EVAL.md with the evaluation results.
"""

import datetime
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app import clock
from app.voice.understand import understand_voice_turn

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = ROOT / "examples" / "voice"
EXPECTED_DIR = SCRIPTS_DIR / "expected"
REPORT_FILE = ROOT / "docs" / "VOICE_EVAL.md"


def get_weekday_date(base_date: datetime.date, weekday_name: str) -> str:
    weekdays = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }
    target = weekdays[weekday_name.lower()]
    days_ahead = (target - base_date.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return str(base_date + datetime.timedelta(days=days_ahead))


def evaluate_dialogue(filepath: Path) -> Tuple[bool, Dict[str, Any]]:
    data = json.loads(filepath.read_text(encoding="utf-8"))
    d_id = data["dialogue_id"]
    title = data["title"]
    turns = data["turns"]
    expected_final = data["expected_final"]

    today = clock.today()
    session_fields: Dict[str, Any] = {}
    confirmed = False
    cancelled = False
    turn_results = []
    current_field = "phone"

    for t in turns:
        t_no = t["turn"]
        text = t["text"]
        expected_ext = t.get("expected_extracted", {})

        # Run understanding orchestrator
        res = understand_voice_turn(text, expected_field=current_field, base_date=today)

        # Merge extracted fields into session
        if res.phone:
            session_fields["phone"] = res.phone
        if res.village:
            session_fields["village"] = res.village
        if res.acres is not None:
            session_fields["acres"] = res.acres
        if res.machine:
            session_fields["machine"] = res.machine
        if res.harvest_date:
            session_fields["harvest_date"] = res.harvest_date

        # Check turn-level extraction match
        turn_passed = True
        for k, v in expected_ext.items():
            if k == "harvest_date_offset_days":
                exp_d = str(today + datetime.timedelta(days=v))
                if res.harvest_date != exp_d:
                    turn_passed = False
            elif k == "harvest_date_weekday":
                exp_d = get_weekday_date(today, v)
                if res.harvest_date != exp_d:
                    turn_passed = False
            elif k == "confirm":
                if res.confirmation != v:
                    turn_passed = False
            elif getattr(res, k, None) != v:
                turn_passed = False

        # State transitions
        if res.confirmation is False:
            if "ਕੈਂਸਲ" in text or "ਰੱਦ" in text or "cancel" in text.lower():
                cancelled = True
            elif res.harvest_date:
                # Revision: update harvest date
                session_fields["harvest_date"] = res.harvest_date
        elif res.confirmation is True:
            confirmed = True

        # Advance current field if needed
        required = ["phone", "village", "acres", "machine", "harvest_date"]
        missing = [f for f in required if f not in session_fields]
        if missing:
            current_field = missing[0]
        elif not confirmed and not cancelled:
            current_field = "confirm"

        turn_results.append({
            "turn": t_no,
            "text": text,
            "passed": turn_passed,
            "extracted": {
                "phone": res.phone,
                "village": res.village,
                "acres": res.acres,
                "machine": res.machine,
                "harvest_date": res.harvest_date,
                "confirmation": res.confirmation,
            },
        })

    # Validate final state
    final_passed = True
    for k, v in expected_final.items():
        if k == "harvest_date_offset_days":
            exp_d = str(today + datetime.timedelta(days=v))
            if session_fields.get("harvest_date") != exp_d:
                final_passed = False
        elif k == "harvest_date_weekday":
            exp_d = get_weekday_date(today, v)
            if session_fields.get("harvest_date") != exp_d:
                final_passed = False
        elif k == "confirmed":
            if confirmed != v:
                final_passed = False
        elif k == "cancelled":
            if cancelled != v:
                final_passed = False
        else:
            if session_fields.get(k) != v:
                final_passed = False

    all_passed = final_passed and all(t["passed"] for t in turn_results)

    return all_passed, {
        "dialogue_id": d_id,
        "title": title,
        "turns_count": len(turns),
        "passed": all_passed,
        "final_state": {
            "fields": session_fields,
            "confirmed": confirmed,
            "cancelled": cancelled,
        },
        "turns": turn_results,
    }


def probe_voice_service() -> Dict[str, Any]:
    url = "http://127.0.0.1:8100/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return {"online": True, "detail": data}
    except Exception:
        pass
    return {"online": False, "detail": None}


def run_evaluation() -> int:
    print("\n" + "=" * 70)
    print("  VAARI VOICE UNDERSTANDING EVALUATION (Step V8)")
    print("=" * 70 + "\n")

    json_files = sorted(EXPECTED_DIR.glob("dialogue*.json"))
    if not json_files:
        print(f"Error: No dialogue test files found in {EXPECTED_DIR}")
        return 1

    total_dialogues = len(json_files)
    passed_dialogues = 0
    results: List[Dict[str, Any]] = []

    for f in json_files:
        ok, res = evaluate_dialogue(f)
        results.append(res)
        status_str = "[PASS]" if ok else "[FAIL]"
        print(f"  {status_str} Dialogue {res['dialogue_id']}: {res['title']} ({res['turns_count']} turns)")
        if not ok:
            print(f"         Final State: {res['final_state']}")
        else:
            passed_dialogues += 1

    accuracy_pct = round(100.0 * passed_dialogues / total_dialogues, 1)
    print("\n" + "-" * 70)
    print(f"  Accuracy: {passed_dialogues}/{total_dialogues} dialogues ({accuracy_pct}%)")

    # Probe live voice service
    service_status = probe_voice_service()
    if service_status["online"]:
        print("  Local Voice Service (http://127.0.0.1:8100): ONLINE")
        print(f"  Model Status: {service_status['detail']}")
    else:
        print("  Local Voice Service (http://127.0.0.1:8100): OFFLINE (Mock / Rule mode active)")
    print("-" * 70 + "\n")

    # Generate/update docs/VOICE_EVAL.md
    write_eval_report(results, accuracy_pct, service_status)

    return 0 if passed_dialogues == total_dialogues else 1


def write_eval_report(results: List[Dict[str, Any]], accuracy_pct: float, service_status: Dict[str, Any]) -> None:
    now_str = clock.iso_z(clock.now_utc())
    lines = [
        "# Voice Booking Evaluation Report",
        "",
        f"**Date**: {now_str}  ",
        "**Pass Bar**: 100% on the 5 realistic farmer dialogues  ",
        f"**Result**: **{accuracy_pct}% ({sum(1 for r in results if r['passed'])}/{len(results)} passed)**  ",
        "",
        "## 1. Dialogue Evaluation Results",
        "",
        "| ID | Dialogue Title | Turns | Status | Extracted Result |",
        "|:---|:---------------|:-----:|:------:|:-----------------|",
    ]

    for r in results:
        status_md = "✅ PASS" if r["passed"] else "❌ FAIL"
        fields = r["final_state"]["fields"]
        conf_str = "Confirmed" if r["final_state"]["confirmed"] else ("Cancelled" if r["final_state"]["cancelled"] else "Open")
        res_summary = f"{conf_str}: {fields.get('phone', '—')}, {fields.get('village', '—')}, {fields.get('acres', '—')}ac, {fields.get('machine', '—')}"
        lines.append(f"| {r['dialogue_id']} | {r['title']} | {r['turns_count']} | {status_md} | {res_summary} |")

    lines.extend([
        "",
        "## 2. Speech Models & Infrastructure",
        "",
        f"- **Local Voice Service Status**: `{'Online' if service_status['online'] else 'Offline / Standalone Mode'}`",
        "- **Speech-to-Text Model**: AI4Bharat IndicConformer (`ai4bharat/indic-conformer-600m-multilingual`, language `pa`)",
        "- **Text-to-Speech Model**: AI4Bharat IndicF5 (`ai4bharat/IndicF5`, pre-cached 16 prompts)",
        "- **Understanding Engine**: Deterministic Python regex and fuzzy matching (app/voice/understand.py, zero LLM reliance)",
        "- **Latency Benchmarks** (from `docs/VOICE_BENCH.md`):",
        "  - IndicConformer STT: **~1.03s** on CPU",
        "  - IndicF5 TTS (Pre-cached WAVs): **< 2ms** response time",
        "",
        "## 3. Evaluation Criteria",
        "",
        "1. **Phone Number Accuracy**: Must correctly resolve 10-digit Indian numbers across Gurmukhi digits, words, and English transliterations.",
        "2. **Fractional Acres**: Must properly map fractional units (ਢਾਈ=2.5, ਡੇਢ=1.5, ਸਾਢੇ=X+0.5, ਸਵਾ=X+0.25, ਪੌਣੇ=X-0.25).",
        "3. **Self-Correction**: If a farmer corrects an acre count or date mid-sentence or in subsequent turns, the updated value must supersede earlier tokens.",
        "4. **Confirmation Gate**: Bookings are never created without affirmative confirmation (`ਹਾਂਜੀ` / `yes` or button tap).",
        "5. **Cancellation**: Farmer request to cancel immediately sets session to cancelled and drops draft state.",
        "",
    ])

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote report to {REPORT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(run_evaluation())
