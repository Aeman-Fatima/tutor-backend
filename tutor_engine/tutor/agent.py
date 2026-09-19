import re
import sys
import anthropic
from tutor.core import (
    tracker, reference as ref_mod, classifier, router,
    templates, filter as filt, verify as verify_mod,
)
client = anthropic.Anthropic()

_reference_cache: dict[str, dict] = {}

_STUCK_STRATEGIES = {"targeted_hint_stuck", "reframe_stuck"}


def run_turn(
    student_id: str,
    problem: dict,
    student_attempt: str,
    conversation: list[dict] | None = None,
    method: str | None = None,
) -> dict:
    """
    Full pipeline for one student turn.

    conversation optional list of prior exchanges, each:
      { "student_attempt": str, "strategy": str, "response": str }
    method       optional solution approach (Change C); passed to generate_reference.

    Returns:
      question, reference, classification, strategy, response,
      srs_skipped, checklist (may be None for follow-up turns)
    """
    question = problem["question"]

    # 1. Generate (or retrieve cached) reference solution
    reference = ref_mod.generate_reference(question, cache=_reference_cache, method=method)

    # 2. Any turn after the first uses the follow-up-aware classifier.
    is_followup_context = bool(conversation)

    # 3. Build deterministic verification checklist (first turns / full attempts only).
    checklist = None
    if not is_followup_context:
        checklist = verify_mod.build_checklist(student_attempt, reference)
        print(f"[verify] {checklist}", file=sys.stderr)

    # 4. Classify
    classification = classifier.classify_attempt(
        question,
        reference,
        student_attempt,
        conversation=conversation,
        is_followup_context=is_followup_context,
        checklist=checklist,
    )
    state       = classification["state"]
    weak_step   = classification.get("weak_step")
    is_followup = classification.get("is_followup", False)

    # 5. Retrieve this student's history on this problem (before recording)
    problem_history = tracker.get_problem_history(student_id, problem["index"])
    attempt_count   = len(problem_history) + 1

    # 6. Route to a strategy
    strategy = router.select_strategy(state, problem_history, is_followup=is_followup)

    # 7. retrieve a similar solved problem for stuck strategies so the
    #    template can include a real worked sub-example. Skip for custom problems.
    similar_example = None
    if strategy in _STUCK_STRATEGIES and problem.get("index", -1) >= 0:
        try:
            from tutor.core import retrieval as retrieval_mod
            hits = retrieval_mod.get_similar(question, exclude_index=problem["index"])
            similar_example = hits[0] if hits else None
        except Exception as exc:
            print(f"[retrieval] {exc}", file=sys.stderr)

    # 8. Build the tutor system prompt from the template
    tutor_system = templates.fill_template(
        strategy, weak_step, attempt_count, similar_example=similar_example
    )

    # 9. Generate the tutor response
    messages = _build_messages(question, student_attempt, conversation)

    draft = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=tutor_system,
        messages=messages,
    ).content[0].text.strip()

    # 10. Deterministic answer-leak check
    if not is_followup and _answer_leak(draft, reference["answer"]):
        print(f"[verify] WARNING: tutor draft may expose answer {reference['answer']!r}", file=sys.stderr)

    # 11. Pedagogical filter — strip any direct answers that slipped through
    response = filt.apply_pedagogical_filter(draft)

    # 12. Record attempt and update SRS — SKIP for follow-up responses
    srs_skipped = bool(is_followup)
    if not srs_skipped:
        tracker.record_attempt(student_id, problem["index"], state)

    return {
        "question":       question,
        "reference":      reference,
        "classification": classification,
        "strategy":       strategy,
        "response":       response,
        "srs_skipped":    srs_skipped,
        "checklist":      checklist,
    }


def _answer_leak(draft: str, reference_answer: str) -> bool:
    """True if the reference answer appears as a standalone number in the draft."""
    clean = reference_answer.strip()
    return bool(re.search(rf"(?<!\d){re.escape(clean)}(?!\d)", draft))


def _build_messages(
    question: str,
    student_attempt: str,
    conversation: list[dict] | None,
) -> list[dict]:
    if not conversation:
        return [{"role": "user", "content": f"Problem: {question}\n\nStudent attempt: {student_attempt}"}]

    msgs: list[dict] = []
    for i, ex in enumerate(conversation):
        prefix = f"Problem: {question}\n\n" if i == 0 else ""
        msgs.append({"role": "user",      "content": f"{prefix}Student: {ex['student_attempt']}"})
        msgs.append({"role": "assistant", "content": ex["response"]})
    msgs.append({"role": "user", "content": f"Student: {student_attempt}"})
    return msgs
