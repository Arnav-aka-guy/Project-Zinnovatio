"""Unit tests for Voice Evaluation Suite (Step V8).

Verifies that:
  - All 5 evaluation scripts in examples/voice/expected/ are loaded and pass with 100% accuracy.
  - The evaluation runner executes cleanly.
"""

from app.voice.eval import EXPECTED_DIR, evaluate_dialogue, run_evaluation


def test_voice_evaluation_all_scripts_pass():
    json_files = sorted(EXPECTED_DIR.glob("dialogue*.json"))
    assert len(json_files) == 5, f"Expected 5 dialogue scripts, found {len(json_files)}"

    for f in json_files:
        ok, res = evaluate_dialogue(f)
        assert ok is True, f"Dialogue {res['dialogue_id']} ({res['title']}) failed: {res['final_state']}"


def test_voice_evaluation_runner():
    exit_code = run_evaluation(write_report=False)
    assert exit_code == 0
