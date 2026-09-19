import os
import sys
from dotenv import load_dotenv

load_dotenv()

from tutor.core.tracker import init_db
from tutor.data.gsm8k_loader import GSM8KLoader
from tutor.agent import run_turn


def main():
    init_db()
    loader = GSM8KLoader()

    student_id = input("Enter your student ID (or press Enter for 'default'): ").strip()
    if not student_id:
        student_id = "default"

    total = loader.size("train")
    print(f"\nGSM8K has {total} training problems.")

    while True:
        raw = input("\nEnter problem number (0-based), or 'q' to quit: ").strip()
        if raw.lower() == "q":
            print("Goodbye!")
            sys.exit(0)

        try:
            idx = int(raw)
        except ValueError:
            print("Please enter a valid integer.")
            continue

        if not (0 <= idx < total):
            print(f"Index must be between 0 and {total - 1}.")
            continue

        problem = loader.get_problem(idx)
        print(f"\n--- Problem {idx} ---")
        print(problem["question"])
        print()

        while True:
            attempt = input("Your attempt (or 'skip' to pick another problem): ").strip()
            if attempt.lower() == "skip":
                break
            if not attempt:
                continue

            result = run_turn(student_id, problem, attempt)

            print(f"\n[Classification: {result['classification']['state']}]")
            print(f"[Strategy: {result['strategy']}]")
            print(f"\nTutor: {result['response']}\n")

            if result["classification"]["state"] == "correct":
                again = input("Solved! Try another problem? (y/n): ").strip().lower()
                if again != "y":
                    sys.exit(0)
                break


if __name__ == "__main__":
    main()
