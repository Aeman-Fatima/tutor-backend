"""
Interactive demo of the AI Math Tutor pipeline.

Shows the full flow for one student attempt:
  1. Display a GSM8K-style problem
  2. Student types their attempt
  3. Generate a CoT reference solution  (claude-sonnet-4-6)
  4. Classify the attempt               (correct / partially_flawed / incorrect)
  5. Route to a pedagogical strategy    (6-strategy router)
  6. Generate a tutor response          (claude-sonnet-4-6)
  7. Apply the pedagogical filter       (claude-haiku-4-5)
  8. Update the SRS card                (SM-2)

Requires ANTHROPIC_API_KEY in .env

Run with:
    python -m tutor.demo_tutor
"""

import os
import sys
from datetime import date
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import tutor.core.srs as srs_mod
import tutor.core.tracker as tracker_mod

# ── now safe to import the rest ───────────────────────────────────────────────
from tutor.core import reference as ref_mod
from tutor.core import classifier
from tutor.core import router
from tutor.core import templates
from tutor.core import filter as filt

import anthropic
client = anthropic.Anthropic()

# ── hardcoded problems (no dataset download needed) ───────────────────────────
PROBLEMS = [
    {
        "index": 0,
        "question": (
            "Janet's ducks lay 16 eggs per day. She eats 3 for breakfast every morning "
            "and bakes muffins for her friends every day with 4 eggs. "
            "She sells the remainder at the farmers' market daily for $2 per fresh duck egg. "
            "How much does she make every day at the farmers' market?"
        ),
        "gold_answer": "18",
    },
    {
        "index": 1,
        "question": (
            "A store had 120 oranges. It sold 35 on Monday and received a new shipment of 50 on Tuesday. "
            "On Wednesday it sold 48 oranges. How many oranges does the store have now?"
        ),
        "gold_answer": "87",
    },
    {
        "index": 2,
        "question": (
            "Tom reads 15 pages every day. His book has 285 pages. "
            "He has already read 60 pages. "
            "How many more days does he need to finish the book?"
        ),
        "gold_answer": "15",
    },
]

STUDENT = "demo_student"
STATE_LABEL = {
    "correct":          "CORRECT",
    "partially_flawed": "PARTIALLY FLAWED",
    "incorrect":        "INCORRECT",
}
STATE_COLOUR = {
    "correct":          "\033[92m",   # green
    "partially_flawed": "\033[93m",   # yellow
    "incorrect":        "\033[91m",   # red
}
RESET = "\033[0m"
BOLD  = "\033[1m"
DIM   = "\033[2m"

_reference_cache: dict[str, dict] = {}


# ── display helpers ───────────────────────────────────────────────────────────

def divider(char="─", width=62):
    print(char * width)

def section(title: str):
    print(f"\n{DIM}{'─' * 62}{RESET}")
    print(f"  {BOLD}{title}{RESET}")
    print(f"{DIM}{'─' * 62}{RESET}")

def coloured_state(state: str) -> str:
    c = STATE_COLOUR.get(state, "")
    return f"{c}{BOLD}{STATE_LABEL[state]}{RESET}"

def print_reference(ref: dict):
    print()
    for i, step in enumerate(ref["steps"], 1):
        print(f"    Step {i}: {step}")
    print(f"    {BOLD}Answer: {ref['answer']}{RESET}")

def spinner_label(msg: str):
    print(f"  {DIM}⟳  {msg}...{RESET}", end="\r", flush=True)

def clear_line():
    print(" " * 60, end="\r")


# ── pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline(problem: dict, attempt: str, verbose: bool) -> dict:
    question = problem["question"]

    # 1. Reference
    spinner_label("Generating reference solution")
    reference = ref_mod.generate_reference(question, cache=_reference_cache)
    clear_line()

    if verbose:
        section("Reference solution (CoT)")
        print_reference(reference)

    # 2. Classify
    spinner_label("Classifying your attempt")
    classification = classifier.classify_attempt(question, reference, attempt)
    clear_line()
    state = classification["state"]
    weak_step = classification.get("weak_step")

    # 3. History + strategy
    problem_history = tracker_mod.get_problem_history(STUDENT, problem["index"])
    attempt_count = len(problem_history) + 1
    strategy = router.select_strategy(state, problem_history)

    # 4. Tutor system prompt
    tutor_system = templates.fill_template(strategy, weak_step, attempt_count)

    # 5. Draft response
    spinner_label("Generating tutor response")
    draft = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=tutor_system,
        messages=[{
            "role": "user",
            "content": f"Problem: {question}\n\nStudent attempt: {attempt}",
        }],
    ).content[0].text.strip()
    clear_line()

    # 6. Pedagogical filter
    spinner_label("Applying pedagogical filter")
    response = filt.apply_pedagogical_filter(draft)
    clear_line()

    # 7. Record + update SRS
    tracker_mod.record_attempt(STUDENT, problem["index"], state)
    srs_card = srs_mod.update_card(STUDENT, problem["index"], state, as_of=date.today())

    return {
        "reference": reference,
        "classification": classification,
        "state": state,
        "weak_step": weak_step,
        "strategy": strategy,
        "response": response,
        "srs_card": srs_card,
        "attempt_count": attempt_count,
    }


# ── main loop ─────────────────────────────────────────────────────────────────

def problem_session(problem: dict, verbose: bool):
    print(f"\n  {BOLD}Problem {problem['index'] + 1}{RESET}")
    divider()
    print(f"  {problem['question']}")
    divider()

    attempt_num = 0
    while True:
        attempt_num += 1
        print(f"\n  {DIM}Attempt #{attempt_num} — type your working and final answer.{RESET}")
        print(f"  {DIM}(or 'skip' to move on, 'ref' to see the reference solution){RESET}\n")

        attempt = input("  Your attempt: ").strip()
        if not attempt:
            continue
        if attempt.lower() == "skip":
            print(f"\n  Skipping. (Gold answer was {problem['gold_answer']})")
            return
        if attempt.lower() == "ref":
            ref = ref_mod.generate_reference(problem["question"], cache=_reference_cache)
            section("Reference solution")
            print_reference(ref)
            continue

        result = run_pipeline(problem, attempt, verbose=(verbose and attempt_num == 1))

        # ── Classification banner ──────────────────────────────────────────
        section("Classification")
        print(f"  State    :  {coloured_state(result['state'])}")
        if result["weak_step"]:
            print(f"  Weak step:  {result['weak_step']}")
        print(f"  Reasoning:  {DIM}{result['classification'].get('reasoning', '')}{RESET}")

        # ── Strategy ──────────────────────────────────────────────────────
        print(f"\n  Strategy :  {BOLD}{result['strategy']}{RESET}  (attempt #{result['attempt_count']})")

        # ── Tutor response ─────────────────────────────────────────────────
        section("Tutor")
        print()
        for line in result["response"].splitlines():
            print(f"    {line}")

        # ── SRS update ────────────────────────────────────────────────────
        card = result["srs_card"]
        section("SRS card updated")
        print(f"  Next review in {BOLD}{card['interval']} day(s){RESET}  "
              f"(ease factor: {card['ease_factor']:.2f},  reps: {card['repetitions']})")

        if result["state"] == "correct":
            print(f"\n  {BOLD}Well done! Problem solved.{RESET}")
            again = input("\n  Try the next problem? (y/n): ").strip().lower()
            return again == "y"

        print()


def main():
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("\n  ERROR: ANTHROPIC_API_KEY not set. Copy .env.example → .env and add your key.\n")
        sys.exit(1)

    print(f"\n{'═' * 62}")
    print(f"  {BOLD}AI Math Tutor — Interactive Demo{RESET}")
    print(f"  Pipeline: CoT reference → classify → route → respond → filter → SRS")
    print(f"{'═' * 62}")

    verbose_input = input("\n  Show reference solution on first attempt? (y/n, default y): ").strip().lower()
    verbose = verbose_input != "n"

    for i, problem in enumerate(PROBLEMS):
        continue_to_next = problem_session(problem, verbose)
        if not continue_to_next and i < len(PROBLEMS) - 1:
            break

    print(f"\n{'═' * 62}")
    print(f"  Session complete. Problems attempted: {len(PROBLEMS)}")
    print(f"  Run 'python -m tutor.demo_srs' to see the full SRS schedule.")
    print(f"{'═' * 62}\n")


if __name__ == "__main__":
    main()
