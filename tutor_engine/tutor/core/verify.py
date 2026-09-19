"""
Deterministic verification checklist for a student's math attempt.

Produces a dict passed to classifier.classify_attempt() as hard constraints:
  - answer_match=False  → classifier CANNOT return 'correct'
  - invalid arithmetic  → classifier should flag the offending step as weak_step
  - approach_score      → embedding cosine similarity against reference steps
"""

import re

try:
    from sentence_transformers import SentenceTransformer, util as st_util
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False

_embedder = None

_OP_PATTERN = re.compile(
    r"([\d,\.]+)\s*([×x\*/÷+\-])\s*([\d,\.]+)\s*=\s*([\d,\.]+)"
)
_NUM_PATTERN = re.compile(r"-?[\d,\.]+")

# Symbolic math expression patterns — most specific first so they shadow bare integers.
# Handles: 6*sqrt(13), 6sqrt(13), sqrt(468), 21.63, 21
_EXPR_PAT = re.compile(
    r"\d+\s*\*\s*sqrt\s*\(\s*\d+\s*\)"
    r"|\d+\s*sqrt\s*\(\s*\d+\s*\)"
    r"|sqrt\s*\(\s*\d+\s*\)"
    r"|-?\d+\.\d+"
    r"|-?\d+",
    re.IGNORECASE,
)

_OP_FN = {
    "×": lambda a, b: a * b,
    "x": lambda a, b: a * b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a / b if b != 0 else None,
    "÷": lambda a, b: a / b if b != 0 else None,
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
}


def _parse_num(text: str) -> float | None:
    """Extract the last meaningful number from text (the student's final answer heuristic)."""
    cleaned = text.replace(",", "").strip()
    matches = _NUM_PATTERN.findall(cleaned)
    for raw in reversed(matches):
        try:
            v = float(raw)
            if v != 0:
                return v
        except ValueError:
            continue
    return None


def _sympy_eval(text: str):
    """
    Extract and evaluate the last numeric or symbolic math expression in text.
    Handles sqrt(468), 6*sqrt(13), 6sqrt(13), 6√13, 21.63, plain integers.
    Returns a sympy expression, or None if nothing parseable is found.
    """
    try:
        import sympy
        t = text.replace("×", "*").replace("÷", "/").replace("−", "-")
        t = re.sub(r"√\(([^)]+)\)", r"sqrt(\1)", t)
        t = re.sub(r"√(\d+)", r"sqrt(\1)", t)
        last_val = None
        for m in _EXPR_PAT.finditer(t):
            try:
                expr = m.group(0).strip().replace(" ", "")
                expr = re.sub(r"(\d)(sqrt)", r"\1*\2", expr, flags=re.IGNORECASE)
                last_val = sympy.sympify(expr)
            except Exception:
                continue
        return last_val
    except Exception:
        return None


def _sympy_compare(student_text: str, ref_text: str) -> bool:
    """Numerically compare two math expressions via sympy.evalf."""
    try:
        import sympy
        sv = _sympy_eval(student_text)
        rv = _sympy_eval(ref_text)
        if sv is None or rv is None:
            return False
        diff = abs(float((sv - rv).evalf()))
        tolerance = max(0.01, abs(float(rv.evalf())) * 1e-3)
        return diff < tolerance
    except Exception:
        return False


def _get_embedder():
    global _embedder
    if _embedder is None and _ST_AVAILABLE:
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


def check_final_answer(student_attempt: str, reference_answer: str) -> bool:
    """True if the student's final answer matches the reference answer.

    Returns True immediately when reference_answer is unavailable ('unknown')
    so the classifier is not hard-constrained when there is nothing to compare against.
    Falls back to sympy evaluation for symbolic/irrational answers (e.g. 6*sqrt(13)).
    """
    if not reference_answer or reference_answer.strip().lower() in ("unknown", ""):
        return True  # indeterminate — let the classifier decide

    # Fast path: plain numeric comparison
    ref_num     = _parse_num(reference_answer)
    student_num = _parse_num(student_attempt)
    if ref_num is not None and student_num is not None:
        if abs(student_num - ref_num) < max(0.01, abs(ref_num) * 1e-6):
            return True

    # Slow path: sympy symbolic/numeric comparison (handles sqrt, irrational answers)
    return _sympy_compare(student_attempt, reference_answer)


def check_arithmetic(student_attempt: str) -> list[dict]:
    """
    Find every "A op B = C" pattern in the student's text and verify it.
    Returns a list of {expression, stated_result, computed_result, valid}.
    """
    results = []
    for m in _OP_PATTERN.finditer(student_attempt):
        a_str, op_str, b_str, stated_str = m.groups()
        try:
            a = float(a_str.replace(",", ""))
            b = float(b_str.replace(",", ""))
            stated = float(stated_str.replace(",", ""))
        except ValueError:
            continue
        fn = _OP_FN.get(op_str)
        computed = fn(a, b) if fn else None
        valid = (
            computed is not None
            and abs(computed - stated) < max(0.01, abs(computed) * 1e-6)
        )
        results.append({
            "expression": f"{a_str} {op_str} {b_str}",
            "stated_result": stated,
            "computed_result": round(computed, 6) if computed is not None else None,
            "valid": valid,
        })
    return results


def check_step_alignment(student_attempt: str, reference_steps: list[str]) -> float:
    """
    Embedding cosine similarity between the student's attempt and the reference steps.
    Returns a score in [0, 1]; returns 0.5 (neutral) if sentence-transformers is unavailable.
    """
    model = _get_embedder()
    if model is None or not reference_steps:
        return 0.5
    ref_text = " ".join(reference_steps)
    embeddings = model.encode([student_attempt, ref_text], convert_to_tensor=True)
    score = st_util.cos_sim(embeddings[0], embeddings[1]).item()
    return round(max(0.0, float(score)), 3)


def build_checklist(student_attempt: str, reference: dict) -> dict:
    """
    Build the full verification checklist for one student attempt.

    Returns:
        student_answer     — the number extracted from the student's text (or None)
        reference_answer   — the reference final answer string
        answer_match       — True if student_answer matches reference_answer;
                             True when reference is 'unknown' (custom/failed generation)
        arithmetic_checks  — per-expression validity list
        approach_score     — float [0, 1] embedding similarity to reference steps
    """
    ref_answer        = reference["answer"]
    arithmetic_checks = check_arithmetic(student_attempt)
    approach_score    = check_step_alignment(student_attempt, reference.get("steps", []))

    ref_unknown = not ref_answer or ref_answer.strip().lower() in ("unknown", "")
    if ref_unknown:
        # No gold answer available (custom problem or LLM generation failed).
        # Use the student's own arithmetic chain as the primary correctness signal.
        answer_match = all(c["valid"] for c in arithmetic_checks) if arithmetic_checks else True
    else:
        answer_match = check_final_answer(student_attempt, ref_answer)

    student_num = _parse_num(student_attempt)
    return {
        "student_answer":    str(student_num) if student_num is not None else None,
        "reference_answer":  ref_answer,
        "answer_match":      answer_match,
        "arithmetic_checks": arithmetic_checks,
        "approach_score":    approach_score,
    }
