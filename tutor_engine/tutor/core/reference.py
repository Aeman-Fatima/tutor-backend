import json
import re

_SYSTEM = (
    "You are a math expert generating a step-by-step reference solution. "
    "Given a math word problem, produce a clear chain-of-thought reasoning trace followed by the final answer. "
    "Respond ONLY with a JSON object containing exactly two keys:\n"
    '  "steps": a list of strings, each being one reasoning step\n'
    '  "answer": the final numeric answer as a string (digits only, no units or commas)\n'
    "Do not include any text outside the JSON object."
)

# Change C: method-specific addendums appended to the base system prompt
_METHOD_ADDENDUMS: dict[str, str] = {
    "algebra":    "Solve using algebra: define a variable for the unknown, write an equation, and solve it symbolically.",
    "unit_rate":  "Solve using the unit rate method: first find the value per single unit, then scale to the required quantity.",
    "proportion": "Solve by setting up a proportion or ratio table, then cross-multiply.",
    "percentage": "Solve by converting values to/from percentage or decimal form at each step.",
}

# Change C: system prompt for method detection
_METHOD_SYSTEM = (
    "You are a math education expert. Given a math word problem, identify which "
    "solution methods are applicable.\n"
    "Return ONLY a JSON array of method name strings. Choose from these methods only:\n"
    '  "direct"     — natural step-by-step arithmetic (always applicable)\n'
    '  "algebra"    — define a variable, set up an equation, solve algebraically\n'
    '  "unit_rate"  — find the unit rate first, then scale up\n'
    '  "proportion" — set up a proportion or ratio table\n'
    '  "percentage" — convert to/from percentage or decimal form\n'
    "Include a method only if it offers a genuinely different approach. "
    "Always include \"direct\". Return 2-3 methods at most. "
    "Return a JSON array only, no other text."
)

_method_cache: dict[str, list[str]] = {}


def detect_methods(question: str) -> list[str]:
    """
    Ask the LLM which solution methods are applicable for this problem.
    Returns a list always containing at least ["direct"].
    Results are cached in memory.
    """
    if question in _method_cache:
        return _method_cache[question]

    from core.llm_client import api_response
    response = api_response(
        _METHOD_SYSTEM,
        prompt_label="Problem: ",
        content_text=question,
        json_mode=True,
    )
    text = _strip_fences(response)
    try:
        methods = json.loads(text)
        if not isinstance(methods, list):
            methods = ["direct"]
    except json.JSONDecodeError:
        methods = ["direct"]

    if "direct" not in methods:
        methods = ["direct"] + methods

    _method_cache[question] = methods
    return methods


def generate_reference(
    question: str,
    cache: dict | None = None,
    method: str | None = None,
) -> dict:
    """
    Generate a CoT reference solution for question.

    method — optional solution approach (Change C). When provided and not "direct",
             the system prompt is extended with a method-specific instruction.
             "other:<text>" passes the text as a free-form approach description.
    """
    method_key = method or "direct"
    cache_key  = f"{question}|||{method_key}"

    if cache is not None and cache_key in cache:
        return cache[cache_key]

    # Build system prompt
    system = _SYSTEM
    if method and method != "direct":
        if method.startswith("other:"):
            approach = method[len("other:"):].strip()
            if approach:
                system = _SYSTEM.rstrip() + f"\n\nApproach: Solve using the following method: {approach}."
        elif method in _METHOD_ADDENDUMS:
            system = _SYSTEM.rstrip() + f"\n\nApproach: {_METHOD_ADDENDUMS[method]}"

    from core.llm_client import api_response
    response = api_response(system, prompt_label="Problem: ", content_text=question, tokens=2048)
    text = _strip_fences(response)
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = {"steps": [text], "answer": "unknown"}

    if cache is not None:
        cache[cache_key] = result

    return result


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()
