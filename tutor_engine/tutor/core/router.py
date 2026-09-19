STRATEGIES = (
    "praise_stretch",
    "praise_consolidate",
    "targeted_hint",
    "targeted_hint_stuck",
    "reframe",
    "reframe_stuck",
    "followup_ack",
    "followup_incorrect",
)


def select_strategy(state: str, problem_history: list[dict], is_followup: bool = False) -> str:
    """
    Return a strategy name based on the current attempt state and the
    student's prior attempts on this specific problem.

    is_followup — True when the classifier determined the student was answering
                  a reflection question rather than re-attempting the problem.
                  In this case we route to followup_ack/followup_incorrect and
                  skip the normal history-based routing.
    """
    if is_followup:
        # Don't loop back into hint/reframe logic for a conversational follow-up
        return "followup_ack" if state == "correct" else "followup_incorrect"

    prior_states  = [h["state"] for h in problem_history]
    attempt_count = len(prior_states)

    if state == "correct":
        if any(s != "correct" for s in prior_states):
            return "praise_consolidate"
        return "praise_stretch"

    if state == "partially_flawed":
        if attempt_count >= 2 and all(s == "partially_flawed" for s in prior_states[-2:]):
            return "targeted_hint_stuck"
        return "targeted_hint"

    # state == "incorrect"
    if attempt_count >= 2 and all(s == "incorrect" for s in prior_states[-2:]):
        return "reframe_stuck"
    return "reframe"
