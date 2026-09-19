"""
Keyword-based topic tagger for GSM8K problems.

Usage:
    python -m tutor.tag_topics              # tag first 40 problems, print result
    python -m tutor.tag_topics --save       # overwrite tutor/data/topics.json
    python -m tutor.tag_topics --count 60   # tag first 60 problems
    python -m tutor.tag_topics --print      # print each problem + assigned topic

Topics: rate, percentage, ratio, geometry, multi_step_arithmetic
"""

import argparse
import json
import os
import re
import sys

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_REPO_ROOT))

TOPICS_PATH = os.path.join(_REPO_ROOT, "data", "topics.json")

# Keywords ordered from most specific to least specific.
# First match wins.
_RULES: list[tuple[str, list[str]]] = [
    ("geometry", [
        r"\barea\b", r"\bperimeter\b", r"\bcircumference\b",
        r"\bradius\b", r"\bdiameter\b", r"\btriangle\b", r"\bsquare\b",
        r"\brectangle\b", r"\bcircle\b", r"\bvolume\b", r"\bangle\b",
        r"\bhypotenuse\b", r"\blength.?width\b", r"\bwidth.?length\b",
    ]),
    ("percentage", [
        r"\bpercent\b", r"\b\d+\s*%\b", r"\bdiscount\b", r"\bsale\b",
        r"\bmark.?up\b", r"\btax\b", r"\btip\b", r"\binterest\b",
    ]),
    ("ratio", [
        r"\bratio\b", r"\bfor every\b", r"\bfor each\b", r"\bto every\b",
        r"\btwice as many\b", r"\bhalf as many\b", r"\bthree times as many\b",
        r"\bscale\b", r"\bproportion\b", r"\bsimplif\b",
        r"\bshared.{0,20}between\b",
    ]),
    ("rate", [
        r"\bper hour\b", r"\bper day\b", r"\bper minute\b", r"\bper mile\b",
        r"\bper week\b", r"\bper gallon\b", r"\bper pound\b", r"\bper page\b",
        r"\ban hour\b", r"\ba day\b", r"\ba week\b", r"\ba minute\b",
        r"\bspeed\b", r"\brate\b", r"\bhow long\b", r"\bhow many hours\b",
        r"\bhow many minutes\b", r"\bkilobits\b", r"\bmegabytes\b",
        r"\boverdrive\b", r"\bovertime\b",
    ]),
]

_DEFAULT_TOPIC = "multi_step_arithmetic"


def classify(question: str) -> str:
    q = question.lower()
    for topic, patterns in _RULES:
        for pat in patterns:
            if re.search(pat, q):
                return topic
    return _DEFAULT_TOPIC


def tag_problems(count: int = 40) -> dict[str, str]:
    from tutor.data.gsm8k_loader import GSM8KLoader
    loader = GSM8KLoader()
    result: dict[str, str] = {}
    for i in range(count):
        p = loader.get_problem(i)
        result[str(i)] = classify(p["question"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save",  action="store_true", help="Overwrite topics.json")
    parser.add_argument("--count", type=int, default=40, help="Number of problems to tag")
    parser.add_argument("--print", action="store_true", dest="verbose", help="Print each problem")
    args = parser.parse_args()

    mapping = tag_problems(args.count)

    if args.verbose:
        from tutor.data.gsm8k_loader import GSM8KLoader
        loader = GSM8KLoader()
        for idx_str, topic in mapping.items():
            q = loader.get_problem(int(idx_str))["question"][:80]
            print(f"[{idx_str:>2}] {topic:<22}  {q}")
    else:
        print(json.dumps(mapping, indent=2))

    if args.save:
        with open(TOPICS_PATH, "w") as f:
            json.dump(mapping, f, indent=2)
        print(f"\nSaved to {TOPICS_PATH}")


if __name__ == "__main__":
    main()
