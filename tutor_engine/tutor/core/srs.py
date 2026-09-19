"""
Spaced Repetition System (SRS) using the SM-2 algorithm, adapted for the
three attempt states produced by the classifier:

    correct         → quality 5  (full recall)
    partially_flawed → quality 3  (hesitant recall)
    incorrect        → quality 1  (complete failure)

SM-2 rules:
  - Each problem per student has a card with: interval (days), ease_factor, repetitions, due_date.
  - After each attempt the card is updated:
      * quality < 3  → reset to interval=1, repetitions=0 (relearn from scratch)
      * quality >= 3 → advance interval and increment repetitions
  - Interval schedule:
      repetitions == 0  → 1 day
      repetitions == 1  → 6 days
      repetitions >= 2  → round(previous_interval * ease_factor)
  - Ease factor update (clamped to minimum 1.3):
      EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
"""

import os
import psycopg2
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

_DATABASE_URL = os.environ.get("DATABASE_URL")

_STATE_TO_QUALITY = {
    "correct": 5,
    "partially_flawed": 3,
    "incorrect": 1,
}

_MIN_EASE = 1.3
_DEFAULT_EASE = 2.5


def _conn():
    return psycopg2.connect(_DATABASE_URL)


def init_srs_db():
    # Schema is managed by tutor-backend/src/db/schema.sql (PostgreSQL).
    # Kept as a no-op so callers don't need to change.
    pass


def _get_or_create_card(cur, student_id: str, problem_idx: int, base_date: date | None = None) -> dict:
    cur.execute(
        "SELECT interval, ease_factor, repetitions, due_date FROM srs_cards "
        "WHERE student_id = %s AND problem_index = %s",
        (student_id, problem_idx),
    )
    row = cur.fetchone()

    if row:
        return {
            "interval": row[0],
            "ease_factor": row[1],
            "repetitions": row[2],
            "due_date": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
        }

    today_str = (base_date or date.today()).isoformat()
    cur.execute(
        "INSERT INTO srs_cards (student_id, problem_index, interval, ease_factor, repetitions, due_date) "
        "VALUES (%s, %s, 1, %s, 0, %s)",
        (student_id, problem_idx, _DEFAULT_EASE, today_str),
    )
    return {"interval": 1, "ease_factor": _DEFAULT_EASE, "repetitions": 0, "due_date": today_str}


def _sm2_update(card: dict, quality: int) -> dict:
    ef = card["ease_factor"]
    reps = card["repetitions"]
    interval = card["interval"]

    new_ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ef = max(_MIN_EASE, new_ef)

    if quality < 3:
        new_reps = 0
        new_interval = 1
    else:
        new_reps = reps + 1
        if new_reps == 1:
            new_interval = 1
        elif new_reps == 2:
            new_interval = 6
        else:
            new_interval = round(interval * new_ef)

    return {
        "interval": new_interval,
        "ease_factor": new_ef,
        "repetitions": new_reps,
    }


def update_card(
    student_id: str,
    problem_idx: int,
    state: str,
    as_of: date | None = None,
) -> dict:
    """
    Update the SRS card for a problem after one attempt.
    `as_of` overrides today's date (useful for simulations/testing).
    Returns the updated card dict.
    """
    quality = _STATE_TO_QUALITY.get(state, 1)
    base_date = as_of or date.today()

    with _conn() as conn:
        with conn.cursor() as cur:
            card = _get_or_create_card(cur, student_id, problem_idx, base_date)
            updated = _sm2_update(card, quality)
            due_date = (base_date + timedelta(days=updated["interval"])).isoformat()
            updated["due_date"] = due_date
            cur.execute(
                "INSERT INTO srs_cards (student_id, problem_index, interval, ease_factor, repetitions, due_date) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (student_id, problem_index) DO UPDATE SET "
                "interval = EXCLUDED.interval, ease_factor = EXCLUDED.ease_factor, "
                "repetitions = EXCLUDED.repetitions, due_date = EXCLUDED.due_date",
                (student_id, problem_idx, updated["interval"], updated["ease_factor"],
                 updated["repetitions"], due_date),
            )

    updated["ease_factor"] = round(updated["ease_factor"], 2)
    return updated


def get_due_problems(student_id: str, as_of: date | None = None) -> list[dict]:
    """
    Return all problems due for review on or before `as_of` (defaults to today).
    Sorted by due_date ascending (most overdue first).
    """
    as_of_str = (as_of or date.today()).isoformat()

    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT problem_index, interval, ease_factor, repetitions, due_date FROM srs_cards "
                "WHERE student_id = %s AND due_date <= %s ORDER BY due_date ASC",
                (student_id, as_of_str),
            )
            rows = cur.fetchall()

    return [
        {
            "problem_index": r[0],
            "interval": r[1],
            "ease_factor": round(r[2], 2),
            "repetitions": r[3],
            "due_date": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
        }
        for r in rows
    ]


def get_current_card(student_id: str, problem_idx: int) -> dict:
    """
    Return the current SRS card without updating it.
    Used when a follow-up response should not trigger an SM-2 update.
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT interval, ease_factor, repetitions, due_date FROM srs_cards "
                "WHERE student_id = %s AND problem_index = %s",
                (student_id, problem_idx),
            )
            row = cur.fetchone()

    if row:
        return {
            "interval": row[0],
            "ease_factor": round(row[1], 2),
            "repetitions": row[2],
            "due_date": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
        }
    return {
        "interval": 1,
        "ease_factor": _DEFAULT_EASE,
        "repetitions": 0,
        "due_date": date.today().isoformat(),
    }


def get_schedule(student_id: str) -> list[dict]:
    """Return all cards for this student, sorted by due_date."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT problem_index, interval, ease_factor, repetitions, due_date FROM srs_cards "
                "WHERE student_id = %s ORDER BY due_date ASC",
                (student_id,),
            )
            rows = cur.fetchall()

    return [
        {
            "problem_index": r[0],
            "interval": r[1],
            "ease_factor": round(r[2], 2),
            "repetitions": r[3],
            "due_date": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
        }
        for r in rows
    ]
