# AI Tutor — Python Pipeline

The core AI pipeline for the tutoring system. It takes a student's free-text math attempt, generates a chain-of-thought reference solution, classifies the attempt into one of three states (correct, partially flawed, incorrect), routes to one of six Socratic response strategies, generates a tutor response, and updates the student's spaced repetition schedule using the SM-2 algorithm.

This pipeline is called by the Node.js backend via `cli_wrapper.py` using a child process. It can also be run standalone for testing.

---

## Prerequisites

- Python 3.11 or higher
- An Anthropic API key (required)
- A Google Gemini API key (only if switching the LLM to Gemini — see below)

---

## Installation

```bash
cd tutor
pip install -r requirements.txt
```

The main dependencies are:

| Package | Version |
|---|---|
| anthropic | >= 0.40.0 |
| google-genai | latest |
| datasets | latest |
| python-dotenv | latest |

---

## Environment Setup

Create a `.env` file inside the `tutor/` folder:

```
ANTHROPIC_API_KEY=your_anthropic_key_here
GOOGLE_API_KEY=your_google_key_here   # only needed if using Gemini
```

---

## Switching the LLM

Open `tutor/core/llm_client.py`. At the top you will see:

```python
# Configuration flag
# LLM = 'gemini'
LLM = 'anthropic'
```

To switch to Gemini, comment out `LLM = 'anthropic'` and uncomment `LLM = 'gemini'`. The rest of the pipeline stays the same. When using Gemini, the model used is `gemini-2.5-flash-lite` with automatic retry on rate limit errors.

**Note:** Switching to Gemini requires a `GOOGLE_API_KEY` in your `.env` file.

---

## Running Standalone (for testing)

Run the interactive demo on 3 hardcoded GSM8K problems:

```bash
cd tutor
python -m tutor.demo_tutor
```

Run the spaced repetition simulation (no LLM calls, deterministic):

```bash
python -m tutor.demo_srs
```

---

## How the Backend Calls This

The Node.js backend spawns `tutor/cli_wrapper.py` as a child process, passes a JSON request via stdin, and reads the JSON response from stdout. You do not need to run this manually — starting the backend handles it automatically.

---

## Project Structure

```
tutor/
  agent.py              # Main orchestrator — run_turn() runs the full pipeline
  cli_wrapper.py        # JSON interface for the Node.js backend
  demo_tutor.py         # Standalone interactive demo
  demo_srs.py           # SM-2 simulation demo
  core/
    classifier.py       # 3-state attempt classifier
    router.py           # 6-strategy response router
    templates.py        # One prompt template per strategy
    reference.py        # Chain-of-thought reference generator
    filter.py           # Pedagogical safety filter (Haiku 4.5)
    srs.py              # SM-2 spaced repetition scheduler
    tracker.py          # Attempt history logger
    llm_client.py       # LLM abstraction layer (Anthropic / Gemini)
    ocr.py              # Image-to-text for handwritten attempts
  data/
    gsm8k_loader.py     # GSM8K dataset loader (Hugging Face)
```