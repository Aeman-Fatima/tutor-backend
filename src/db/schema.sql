-- Math Tutor — PostgreSQL schema
-- Run once: psql $DATABASE_URL -f src/db/schema.sql

CREATE TABLE IF NOT EXISTS attempts (
    id            SERIAL PRIMARY KEY,
    student_id    TEXT        NOT NULL,
    problem_index INTEGER     NOT NULL,
    state         TEXT        NOT NULL CHECK (state IN ('correct', 'partially_flawed', 'incorrect')),
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_attempts_student_problem
    ON attempts (student_id, problem_index);

CREATE TABLE IF NOT EXISTS srs_cards (
    student_id    TEXT    NOT NULL,
    problem_index INTEGER NOT NULL,
    interval      INTEGER NOT NULL DEFAULT 1,
    ease_factor   REAL    NOT NULL DEFAULT 2.5,
    repetitions   INTEGER NOT NULL DEFAULT 0,
    due_date      DATE    NOT NULL DEFAULT CURRENT_DATE,
    PRIMARY KEY (student_id, problem_index)
);
