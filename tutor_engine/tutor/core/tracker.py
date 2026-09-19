import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

_DATABASE_URL = os.environ.get("DATABASE_URL")


def _conn():
    return psycopg2.connect(_DATABASE_URL)


def init_db():
    # Schema is managed by tutor-backend/src/db/schema.sql (PostgreSQL).
    # This is kept as a no-op so callers don't need to change.
    pass


def record_attempt(student_id: str, problem_index: int, attempt_state: str):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO attempts (student_id, problem_index, state) VALUES (%s, %s, %s)",
                (student_id, problem_index, attempt_state),
            )


def get_history(student_id: str, limit: int = 10) -> list[dict]:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT problem_index, state, timestamp FROM attempts "
                "WHERE student_id = %s ORDER BY id DESC LIMIT %s",
                (student_id, limit),
            )
            rows = cur.fetchall()
    return [{"problem_index": r[0], "state": r[1], "timestamp": r[2].isoformat()} for r in rows]


def get_problem_history(student_id: str, problem_index: int) -> list[dict]:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT state, timestamp FROM attempts "
                "WHERE student_id = %s AND problem_index = %s ORDER BY id ASC",
                (student_id, problem_index),
            )
            rows = cur.fetchall()
    return [{"state": r[0], "timestamp": r[1].isoformat()} for r in rows]
