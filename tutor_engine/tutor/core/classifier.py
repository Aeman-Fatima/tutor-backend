import json
import re
import anthropic
client = anthropic.Anthropic()

# Strategies that end with a question the student is expected to answer.
# Replies to ANY of these should be tested for follow-up intent before being
# evaluated against the full reference solution.
#
# REFLECTION_STRATEGIES  — praise turns that ask the student to explain/extend.
# HINT_STRATEGIES        — Socratic turns that ask the student to correct a sub-step.
# QUESTION_POSING_STRATEGIES = their union — the full set used for follow-up detection.
REFLECTION_STRATEGIES = {"praise_stretch", "praise_consolidate"}
HINT_STRATEGIES = {"targeted_hint", "targeted_hint_stuck", "reframe", "reframe_stuck"}
QUESTION_POSING_STRATEGIES = REFLECTION_STRATEGIES | HINT_STRATEGIES

_SYSTEM_NORMAL = (
    "You are an expert math tutor evaluating a student's attempt at a word problem.\n\n"
    "You will receive:\n"
    "  1. The problem statement\n"
    "  2. A reference solution with numbered steps and the correct final answer\n"
    "  3. The student's attempt\n"
    "  4. (Optional) A verification checklist with deterministic pre-computed findings\n\n"
    "DETERMINISTIC PRE-CHECKS (when a 'Verification checklist' section is present):\n"
    "These findings are computed deterministically and are hard constraints:\n"
    "  • answer_match = false → you CANNOT return \"correct\" — the student's final\n"
    "    number does not match the reference answer, regardless of reasoning.\n"
    "  • Any arithmetic_check with valid=false → that expression is a confirmed\n"
    "    arithmetic error; use it as weak_step and prefer \"partially_flawed\" over\n"
    "    \"incorrect\" if the overall approach is otherwise sound.\n"
    "  • approach_score < 0.3 → the student's approach diverges significantly from\n"
    "    the reference steps; lean toward \"incorrect\".\n\n"
    "STEP 1 — Extract the student's final numeric answer.\n"
    "The student may express their answer in any of these forms — handle all of them:\n"
    "  • A bare number:                  '18'\n"
    "  • A number with units:            '18 dollars', '$18', '18 eggs'\n"
    "  • Embedded in a sentence:         'so she makes 18 dollars' or 'the answer is 18'\n"
    "  • A spelled-out word:             'eighteen' → 18\n"
    "  • A number with commas/decimals:  '1,200' → 1200, '18.0' → 18\n"
    "  • The result of a stated calculation: '9 x 2 = 18' → final value is 18\n"
    "If the student gives NO numeric answer at all (only partial working with no conclusion),\n"
    "treat their answer as absent — do not invent one.\n\n"
    "STEP 2 — Compare numerically.\n"
    "Compare the extracted numeric value against the reference final answer.\n"
    "Ignore units, currency symbols, commas, trailing zeros, and phrasing.\n"
    "Example: student '18 dollars' vs reference '18' → they match.\n\n"
    "STEP 3 — Classify into exactly one of three states:\n"
    '  "correct"          — extracted answer matches the reference answer numerically\n'
    '                       AND the reasoning approach aligns with the reference steps\n'
    '  "partially_flawed" — overall approach is on track but there is a localised error\n'
    "                       (wrong arithmetic on one step, one missing step, or correct\n"
    "                       operations applied to wrong intermediate values)\n"
    '  "incorrect"        — fundamentally wrong approach, wrong operations chosen,\n'
    "                       or no numeric answer was provided\n\n"
    "Respond ONLY with a JSON object with exactly these keys:\n"
    '  "state":       one of the three strings above\n'
    '  "weak_step":   the specific step description where the error occurs, or null if correct\n'
    '  "reasoning":   a brief (one-sentence) explanation of your classification\n'
    '  "is_followup": false\n'
    "Do not include any text outside the JSON object.\n"
    "Do not wrap the JSON in markdown code fences."
)

_SYSTEM_FOLLOWUP = (
    "You are an expert math tutor evaluating a student's message in an ongoing tutoring conversation.\n\n"
    "You will receive:\n"
    "  1. The original problem statement\n"
    "  2. A reference solution\n"
    "  3. The conversation so far (student attempts and tutor responses)\n"
    "  4. The student's latest message\n\n"
    "CRITICAL PRE-CHECK — Do this before anything else:\n"
    "The most recent tutor response asked the student a question. It may be:\n"
    "  • A guiding/hint question about a specific sub-step "
    "(e.g., 'How many letters does he write to each friend per week?')\n"
    "  • A scaffolding question that breaks the problem into one small part "
    "(e.g., 'Let's focus on step 1 only: what is 2 × 2?')\n"
    "  • A reflective question asking the student to explain their reasoning "
    "(e.g., 'Can you explain in your own words how you got that?')\n\n"
    "Determine whether the student's latest message is:\n\n"
    "  (A) ANSWERING the tutor's question — any reply that does not deliver a complete "
    "solution to the ORIGINAL problem. This includes: computing a sub-step, explaining "
    "reasoning, showing partial working, giving an intermediate result, or continuing to "
    "refine an answer. Length does not matter — a long multi-sentence reply that never "
    "reaches the original problem's final answer is still (A).\n"
    "  (B) SUBMITTING A FRESH FULL ATTEMPT — a reply that provides the final numeric "
    "answer to the ORIGINAL problem, accompanied by enough working to show a complete "
    "new solution from scratch.\n\n"
    "KEY DISAMBIGUATION RULE — base this decision ONLY on the final answer:\n"
    "  → (B) ONLY IF the reply explicitly states the final answer to the original problem "
    "(a number matching or very close to the reference final answer) AND shows enough "
    "working to be a complete attempt. A reply that reaches the correct final answer "
    "by extending sub-steps counts as (B).\n"
    "  → (A) in ALL OTHER CASES — regardless of reply length. Any reply that stops "
    "short of the original problem's final answer, shows only partial working, or "
    "continues a sub-step dialogue is (A).\n\n"
    "If (A) — the student is answering the tutor's question:\n"
    '  → Set "is_followup": true\n'
    "  → Classify based on whether the student's answer to THAT question is correct:\n"
    '       "correct"   — the sub-answer or explanation is accurate and makes sense\n'
    '       "incorrect" — the sub-answer is wrong, confused, or misses the point\n'
    "  → IMPORTANT: use ONLY \"correct\" or \"incorrect\" — never \"partially_flawed\".\n"
    "    A sub-step answer that does not include the full problem solution is NOT partially "
    "flawed — the student was asked about one step, not the whole problem. "
    "Absence of the final answer is expected, not a flaw.\n"
    '  → Set "weak_step": null\n'
    '  → Set "reasoning" to note this is a follow-up response and what was right/wrong\n\n'
    "If (B) — the student is re-attempting the problem:\n"
    '  → Set "is_followup": false\n'
    "  → Apply the normal classification steps below against the reference solution.\n\n"
    "NORMAL CLASSIFICATION (only if is_followup is false):\n"
    "STEP 1 — Extract the student's final numeric answer (handle embedded sentences, "
    "spelled-out words, units, commas, or results of stated calculations).\n"
    "STEP 2 — Compare numerically against the reference final answer (ignore units/formatting).\n"
    "STEP 3 — Classify:\n"
    '  "correct"          — answer matches AND reasoning aligns with reference steps\n'
    '  "partially_flawed" — approach on track but localised error\n'
    '  "incorrect"        — wrong approach, wrong operations, or no answer given\n\n'
    "Respond ONLY with a JSON object with exactly these keys:\n"
    '  "state":       one of "correct", "partially_flawed", "incorrect"\n'
    '  "weak_step":   step description where error occurs, or null\n'
    '  "reasoning":   one-sentence explanation\n'
    '  "is_followup": true or false\n'
    "Do not include any text outside the JSON object.\n"
    "Do not wrap the JSON in markdown code fences."
)


def classify_attempt(
    question: str,
    reference: dict,
    student_attempt: str,
    conversation: list[dict] | None = None,
    is_followup_context: bool = False,
    checklist: dict | None = None,
) -> dict:
    """
    Classify a student's attempt.

    conversation        — list of prior exchanges: [{student_attempt, strategy, response}, ...]
    is_followup_context — True when there is any prior conversation (i.e., bool(conversation)).
                          Uses _SYSTEM_FOLLOWUP so the classifier can decide whether the
                          student is answering the tutor's ongoing question (A) or submitting
                          a fresh full attempt (B), regardless of which strategy triggered
                          the last tutor turn.
    checklist           — optional dict from verify.build_checklist(); injected into the
                          normal-classification prompt as deterministic constraints. Ignored
                          for follow-up turns (sub-step answers, not full attempts).
    """
    ref_lines = "\n".join(f"Step {i+1}: {s}" for i, s in enumerate(reference["steps"]))
    ref_text  = f"{ref_lines}\nFinal answer: {reference['answer']}"

    if is_followup_context and conversation:
        system_prompt = _SYSTEM_FOLLOWUP

        # Build conversation thread for context
        thread_lines = []
        for i, ex in enumerate(conversation):
            thread_lines.append(f"Student attempt {i+1}: {ex['student_attempt']}")
            thread_lines.append(f"Tutor response {i+1} (strategy={ex['strategy']}): {ex['response']}")
        thread_text = "\n".join(thread_lines)

        prompt = (
            f"Problem: {question}\n\n"
            f"Reference solution:\n{ref_text}\n\n"
            f"Conversation so far:\n{thread_text}\n\n"
            f"Student's latest message:\n{student_attempt}"
        )
        system = [{"type": "text", "text": system_prompt}]
    else:
        system_prompt = _SYSTEM_NORMAL
        prompt = (
            f"Problem: {question}\n\n"
            f"Reference solution:\n{ref_text}\n\n"
            f"Student attempt:\n{student_attempt}"
        )
        if checklist:
            invalid = [
                c for c in checklist.get("arithmetic_checks", []) if not c["valid"]
            ]
            invalid_str = (
                "; ".join(
                    f"{c['expression']} = {c['stated_result']} "
                    f"(should be {c['computed_result']})"
                    for c in invalid
                )
                if invalid else "none"
            )
            prompt += (
                f"\n\nVerification checklist:"
                f"\n  answer_match: {str(checklist['answer_match']).lower()}"
                f"\n  invalid_arithmetic: {invalid_str}"
                f"\n  approach_score: {checklist['approach_score']}"
                f" (0=very different approach, 1=closely aligned)"
            )
        system = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]

    # response = client.messages.create(
    #     model="claude-sonnet-4-6",
    #     max_tokens=512,
    #     system=system,
    #     messages=[{"role": "user", "content": prompt}],
    # )
    from core.llm_client import api_response
    response = api_response(system, user_message=prompt, json_mode=False, model="claude-sonnet-4-6", tokens=512)
    text = _strip_fences(response)
    try:
        result = json.loads(text)
        # Ensure is_followup is always present (default False for safety)
        result.setdefault("is_followup", False)
        return result
    except json.JSONDecodeError:
        return {"state": "incorrect", "weak_step": None, "reasoning": text, "is_followup": False}


def _strip_fences(text: str) -> str:
    """Remove markdown code fences that the model sometimes wraps JSON in."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()
