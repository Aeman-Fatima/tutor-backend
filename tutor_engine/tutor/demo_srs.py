"""
Standalone demo of the Spaced Repetition System module.

Simulates a student working through 5 problems across multiple sessions,
showing how the review schedule evolves based on their performance.

Run with:
    python -m tutor.demo_srs
"""

import os
from datetime import date, timedelta
from dotenv import load_dotenv

# Load DATABASE_URL so srs module can connect to Postgres
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import tutor.core.srs as srs

# ── helpers ──────────────────────────────────────────────────────────────────

STUDENT = "demo_student"

PROBLEMS = {
    0: "Janet's ducks lay 16 eggs per day. She eats 3 for breakfast and bakes 4 into muffins. How many eggs does she sell daily?",
    1: "A store has 120 apples. It sells 35 on Monday and 48 on Tuesday. How many remain?",
    2: "Tom runs 5 miles each morning. How many miles does he run in 2 weeks?",
    3: "A recipe needs 3 cups of flour per batch. How many cups for 7 batches?",
    4: "Sara has $50. She buys a book for $12 and a pen for $3. How much is left?",
}

STATE_EMOJI = {
    "correct": "✓",
    "partially_flawed": "~",
    "incorrect": "x",
}


def header(text: str):
    print(f"\n{'─' * 60}")
    print(f"  {text}")
    print(f"{'─' * 60}")


def print_schedule(as_of: date):
    schedule = srs.get_schedule(STUDENT)
    if not schedule:
        print("  (no cards yet)")
        return

    print(f"  {'Problem':>8}  {'Due':>12}  {'Interval':>10}  {'Reps':>5}  {'Ease':>6}")
    print(f"  {'-------':>8}  {'---':>12}  {'--------':>10}  {'----':>5}  {'----':>6}")
    for card in schedule:
        due = date.fromisoformat(card["due_date"])
        delta = (due - as_of).days
        if delta < 0:
            when = f"overdue {-delta}d"
        elif delta == 0:
            when = "TODAY"
        else:
            when = f"in {delta}d"
        print(
            f"  P{card['problem_index']:>7}  {card['due_date']:>12}  "
            f"{card['interval']:>7} days  {card['repetitions']:>5}  {card['ease_factor']:>6.2f}"
            f"  ({when})"
        )


def simulate_session(session_num: int, sim_date: date, attempts: list[tuple[int, str]]):
    """attempts: list of (problem_idx, state)"""
    header(f"Session {session_num}  —  {sim_date.isoformat()}")

    for prob_idx, state in attempts:
        updated = srs.update_card(STUDENT, prob_idx, state, as_of=sim_date)

        emoji = STATE_EMOJI[state]
        print(
            f"  [{emoji}] P{prob_idx} — {state:16s}  "
            f"→ next review in {updated['interval']:>2} day(s)  "
            f"(EF={updated['ease_factor']:.2f})"
        )

    print("\n  Schedule after this session:")
    print_schedule(sim_date)


def print_due_today(as_of: date):
    due = srs.get_due_problems(STUDENT, as_of=as_of)
    if not due:
        print(f"\n  No problems due on {as_of}.")
    else:
        labels = [f"P{d['problem_index']}" for d in due]
        print(f"\n  Problems due on {as_of}: {labels}")


# ── simulation ───────────────────────────────────────────────────────────────

def main():
    today = date.today()

    print("\n")
    print("       Spaced Repetition Demo            ")
    print(" Algorithm: SM-2 (SuperMemo 2), adapted for 3 states     ")
    print("  States: ✓ correct  ~  partially_flawed  x incorrect     ")

    # Session 1: student sees all 5 problems for the first time
    simulate_session(
        session_num=1,
        sim_date=today,
        attempts=[
            (0, "incorrect"),
            (1, "correct"),
            (2, "partially_flawed"),
            (3, "correct"),
            (4, "incorrect"),
        ],
    )

    # Session 2: one week later — several problems are due
    day7 = today + timedelta(days=7)
    header(f"Fast-forward to {day7.isoformat()} (7 days later)")
    print_due_today(day7)

    simulate_session(
        session_num=2,
        sim_date=day7,
        attempts=[
            (0, "partially_flawed"),
            (2, "correct"),
            (4, "correct"),
        ],
    )

    # Session 3: two weeks from start
    day14 = today + timedelta(days=14)
    header(f"Fast-forward to {day14.isoformat()} (14 days later)")
    print_due_today(day14)

    simulate_session(
        session_num=3,
        sim_date=day14,
        attempts=[
            (0, "correct"),
            (1, "correct"),
            (3, "correct"),
        ],
    )

    # Final view
    header("Final schedule — all 5 problems")
    print_schedule(day14)


if __name__ == "__main__":
    main()
