import anthropic
client = anthropic.Anthropic()

_SYSTEM = (
    "You are a pedagogical safety filter for a math tutor. "
    "You will receive a draft tutor response. Your job is to rewrite it so that it contains "
    "NO direct answers, NO final numeric values, and NO fully worked solutions. "
    "Preserve the tone, structure, and any guiding questions. "
    "If the draft already contains no direct answers, return it unchanged. "
    "Return ONLY the rewritten response — no preamble, no explanation."
)


def apply_pedagogical_filter(draft: str) -> str:
    # response = client.messages.create(
    #     model="claude-haiku-4-5",
    #     max_tokens=512,
    #     system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
    #     messages=[{"role": "user", "content": f"Draft:\n{draft}"}],
    # )
    from core.llm_client import api_response
    response = api_response(
        _SYSTEM,
        prompt_label="Draft:\n",
        content_text=draft,
        model="claude-haiku-4-5",
        tokens=512,
        json_mode=False,  # filter returns plain text, not JSON
    )
    return response
