"""
Thin CLI wrapper around agent.run_turn.
Reads a JSON request from stdin, writes a JSON response to stdout.
Used by the Node backend via child_process.spawn.

Input JSON (GSM8K problem):
  {
    "student_id":      "string",
    "problem_index":   0,
    "student_attempt": "string",
    "conversation":    [...],   ← optional
    "method":          "direct" ← optional (Change C)
  }

Input JSON (custom problem — Change B):
  {
    "student_id":      "string",
    "custom_problem":  "string",
    "student_attempt": "string",
    "conversation":    [...],   ← optional
    "method":          "direct" ← optional
  }

Output JSON on success:
  {
    "ok":             true,
    "question":       "string",
    "reference":      { "steps": [...], "answer": "string" },
    "classification": { "state": "...", "weak_step": "...", "reasoning": "...", "is_followup": false },
    "strategy":       "string",
    "response":       "string",
    "srs_card":       { "interval": 1, "ease_factor": 2.5, "repetitions": 0, "due_date": "..." },
    "srs_skipped":    false
  }

Output JSON on error:
  { "ok": false, "error": "string" }
"""

import sys
import os
import json
from datetime import date

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_REPO_ROOT, "tutor", ".env"))


def main():
    try:
        raw = sys.stdin.read()
        req = json.loads(raw)
    except Exception as e:
        sys.stdout.write(json.dumps({"ok": False, "error": f"Invalid JSON input: {e}"}))
        sys.exit(0)

    try:
        student_id      = req["student_id"]
        student_attempt = req["student_attempt"]
    except KeyError as e:
        sys.stdout.write(json.dumps({"ok": False, "error": f"Missing field: {e}"}))
        sys.exit(0)

    # Change B: accept either problem_index (GSM8K) or custom_problem (free text)
    problem_index_raw = req.get("problem_index")
    custom_problem    = req.get("custom_problem")
    method            = req.get("method")  # Change C: optional solution method

    if problem_index_raw is None and not custom_problem:
        sys.stdout.write(json.dumps({
            "ok": False,
            "error": "Either problem_index or custom_problem is required",
        }))
        sys.exit(0)

    conversation = req.get("conversation") or []

    try:
        from tutor.core import tracker, srs as srs_mod
        from tutor import agent

        tracker.init_db()
        srs_mod.init_srs_db()

        if custom_problem:
            # Change B: build a synthetic problem dict for user-provided text
            from tutor.tag_topics import classify as classify_topic
            problem = {
                "index":        -1,
                "question":     custom_problem,
                "topic":        classify_topic(custom_problem),
                "gold_solution": None,
                "gold_answer":   None,
            }
            is_custom = True
        else:
            from tutor.data.gsm8k_loader import GSM8KLoader
            problem_index = int(problem_index_raw)
            loader  = GSM8KLoader()
            problem = loader.get_problem(problem_index, split="train")
            is_custom = False

        # Change C: pass method to run_turn
        result = agent.run_turn(
            student_id,
            problem,
            student_attempt,
            conversation=conversation,
            method=method,
        )

        # SRS update — skip for follow-ups and for custom problems
        if result.get("srs_skipped") or is_custom:
            srs_card = {
                "interval":    0,
                "ease_factor": 2.5,
                "repetitions": 0,
                "due_date":    str(date.today()),
            }
        else:
            srs_card = srs_mod.update_card(
                student_id,
                problem["index"],
                result["classification"]["state"],
                as_of=date.today(),
            )

        out = {
            "ok":             True,
            "question":       result["question"],
            "reference":      result["reference"],
            "classification": result["classification"],
            "strategy":       result["strategy"],
            "response":       result["response"],
            "srs_card":       srs_card,
            "srs_skipped":    result.get("srs_skipped", False) or is_custom,
            "topic":          problem.get("topic"),
        }
        sys.stdout.write(json.dumps(out))

    except Exception as e:
        import traceback
        sys.stdout.write(json.dumps({"ok": False, "error": str(e), "trace": traceback.format_exc()}))

    sys.exit(0)


if __name__ == "__main__":
    main()
