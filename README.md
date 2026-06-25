# AI Tutor — Node.js Backend

Express/TypeScript REST API that sits between the Angular frontend and the Python pipeline. It receives student attempts from the frontend, spawns the Python pipeline as a child process, mirrors the results into PostgreSQL, and exposes endpoints for problem lists, attempt history, SRS schedules, and OCR.

---

## Prerequisites

- Node.js 20 or higher
- npm 9 or higher
- PostgreSQL 14 or higher (running locally or remote)
- Python pipeline set up and working (see `tutor/README.md`)

---

## Installation

```bash
cd tutor-backend
npm install
```

---

## Environment Setup

Create a `.env` file in `tutor-backend/`:

```
DATABASE_URL=postgresql://username:password@localhost:5432/tutor_db
TUTOR_ROOT=/absolute/path/to/the/parent/folder
PYTHON_PATH=python3
PORT=3000
```

- `DATABASE_URL` — your PostgreSQL connection string
- `TUTOR_ROOT` — absolute path to the folder that contains the `tutor/` folder (one level up from `tutor/`)
- `PYTHON_PATH` — path to your Python executable, defaults to `python3`
- `PORT` — optional, defaults to 3000

---

## Database Setup

Run this once to create the tables:

```bash
npm run db:init
```

This runs `src/db/schema.sql` against your PostgreSQL database and creates the `attempts` and `srs_cards` tables.

---

## Running

Development (auto-restarts on file changes):

```bash
npm run dev
```

Production:

```bash
npm run build
npm start
```

The server runs on `http://localhost:3000` by default.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/attempt` | Submit a student attempt, runs the full pipeline |
| GET | `/api/problems` | List available GSM8K problems |
| GET | `/api/history/:student_id/:problem_index` | Attempt history for a student on a problem |
| GET | `/api/srs/:student_id` | Full SRS schedule for a student |
| POST | `/api/ocr` | Extract text from a handwritten attempt image |
| GET | `/api/health` | Health check |

---

## Project Structure

```
tutor-backend/
  src/
    index.ts            # Express app entry point
    python.ts           # Spawns Python pipeline via cli_wrapper.py
    db/
      pool.ts           # PostgreSQL connection pool
      schema.sql        # Database schema (run once with db:init)
    routes/
      attempt.ts        # POST /api/attempt
      problems.ts       # GET /api/problems
      history.ts        # GET /api/history
      srs.ts            # GET /api/srs
      ocr.ts            # POST /api/ocr
```

---

## Running the Full Project

Start services in this order:

1. Make sure PostgreSQL is running and `npm run db:init` has been run
2. Start the backend: `npm run dev`
3. Start the frontend: `npm start` (from `tutor-frontend/`)
