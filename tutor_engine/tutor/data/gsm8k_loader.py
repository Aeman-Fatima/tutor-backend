import json
import os
import re
from datasets import load_dataset

_TOPICS_PATH = os.path.join(os.path.dirname(__file__), "topics.json")

with open(_TOPICS_PATH) as _f:
    _TOPICS: dict[str, str] = json.load(_f)


class GSM8KLoader:
    def __init__(self):
        self._dataset = None

    def _load(self):
        if self._dataset is None:
            self._dataset = load_dataset("openai/gsm8k", "main")

    def get_problem(self, index: int, split: str = "train") -> dict:
        self._load()
        item = self._dataset[split][index]
        return {
            "index": index,
            "question": item["question"],
            "gold_solution": item["answer"],
            "gold_answer": self._extract_gold(item["answer"]),
            "topic": _TOPICS.get(str(index), "multi_step_arithmetic"),
        }

    def _extract_gold(self, answer_text: str) -> str:
        match = re.search(r"####\s*(.+)$", answer_text, re.MULTILINE)
        if match:
            return match.group(1).strip().replace(",", "")
        return answer_text.strip()

    def size(self, split: str = "train") -> int:
        self._load()
        return len(self._dataset[split])
