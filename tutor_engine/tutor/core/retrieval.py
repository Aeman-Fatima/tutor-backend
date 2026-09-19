"""
Change D — RAG retrieval for stuck hints.

Embeds the first 40 GSM8K problems once (lazy, on first call) and finds
the most similar ones to feed as a worked sub-example into stuck strategies.
Uses in-memory cosine similarity via numpy (no FAISS needed for 40 items).
"""

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False

_PROBLEM_COUNT = 40

_embedder:   SentenceTransformer | None = None
_embeddings: np.ndarray | None         = None   # shape (N, D), L2-normalised
_problems:   list[dict] | None         = None   # {index, question, gold_solution, answer, topic}


def _load() -> None:
    global _embedder, _embeddings, _problems
    if _embeddings is not None:
        return

    if not _ST_AVAILABLE:
        _problems   = []
        _embeddings = np.zeros((0, 1))
        return

    try:
        from tutor.data.gsm8k_loader import GSM8KLoader
    except ImportError:
        from data.gsm8k_loader import GSM8KLoader

    loader    = GSM8KLoader()
    _embedder = SentenceTransformer("all-MiniLM-L6-v2")

    problems: list[dict] = []
    texts:    list[str]  = []

    for i in range(_PROBLEM_COUNT):
        p = loader.get_problem(i)
        problems.append({
            "index":        i,
            "question":     p["question"],
            "gold_solution": p["gold_solution"],
            "answer":       p["gold_answer"],
            "topic":        p["topic"],
        })
        texts.append(p["question"])

    _problems = problems
    raw = _embedder.encode(texts, show_progress_bar=False)
    norms = np.linalg.norm(raw, axis=1, keepdims=True)
    _embeddings = raw / np.maximum(norms, 1e-9)


def get_similar(
    question: str,
    exclude_index: int = -1,
    k: int = 1,
) -> list[dict]:
    """
    Return up to k problems most similar to question from the embedded GSM8K set.
    Excludes the problem at exclude_index (the current problem).
    Returns [] if sentence-transformers is unavailable.

    Each result: {index, question, gold_solution, answer, topic}
    """
    _load()

    if _embeddings is None or _problems is None or len(_problems) == 0:
        return []

    q_raw  = _embedder.encode([question], show_progress_bar=False)
    q_norm = np.linalg.norm(q_raw)
    q_emb  = q_raw / max(q_norm, 1e-9)

    scores = (_embeddings @ q_emb.T).flatten()

    if 0 <= exclude_index < len(scores):
        scores[exclude_index] = -1.0

    top_idx = np.argsort(scores)[::-1][:k]
    return [_problems[i] for i in top_idx if scores[i] > 0]
