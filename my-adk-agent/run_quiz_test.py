#!/usr/bin/env python3
"""
One full quiz test run: start_quiz -> submit_answer for each question -> get_quiz_status -> reset_quiz.
Uses mock state (no LLM, no network). Run from my-adk-agent/:  python3 run_quiz_test.py
"""
from quizzing_agent.agent import start_quiz, submit_answer, get_quiz_status, reset_quiz


class MockToolContext:
    def __init__(self):
        self.state = {}


def main():
    ctx = MockToolContext()
    ctx.state["generated_quiz"] = {
        "quiz_title": "AP Chem Unit 6 – Thermochemistry (test run)",
        "questions": [
            {
                "question_text": "What symbol is used for enthalpy change?",
                "options": ["A) q", "B) ΔH", "C) ΔS", "D) G"],
                "correct_answer": "B) ΔH",
                "correct_choice": "B",
                "explanation": "ΔH is the standard symbol for enthalpy change.",
                "concept": "Enthalpy",
            },
            {
                "question_text": "In an exothermic reaction, heat is _____.",
                "options": ["A) absorbed", "B) released", "C) unchanged", "D) stored"],
                "correct_answer": "B) released",
                "correct_choice": "B",
                "explanation": "Exothermic means heat is released to the surroundings.",
                "concept": "Exothermic reactions",
            },
            {
                "question_text": "What is the first law of thermodynamics?",
                "options": ["A) Energy is conserved", "B) Entropy increases", "C) Heat flows cold to hot", "D) Mass is conserved"],
                "correct_answer": "A) Energy is conserved",
                "correct_choice": "A",
                "explanation": "The first law states energy cannot be created or destroyed.",
                "concept": "First law",
            },
        ],
    }

    print("=== 1. start_quiz ===")
    out = start_quiz(ctx)
    print(out)
    if out.get("status") != "started":
        print("Aborting: start_quiz failed.")
        return
    print()

    answers = ["B", "B", "a"]  # B, B, and "a" (should match "A" with normalization)
    for i, ans in enumerate(answers):
        print(f"=== 2.{i+1} submit_answer({ans!r}) ===")
        out = submit_answer(ctx, ans)
        print(out)
        print()

    print("=== 3. get_quiz_status ===")
    out = get_quiz_status(ctx)
    print(out)
    print()

    print("=== 4. reset_quiz ===")
    out = reset_quiz(ctx)
    print(out)
    print()

    print("=== 5. get_quiz_status after reset ===")
    out = get_quiz_status(ctx)
    print(out)
    print("\nDone. Test run completed.")


if __name__ == "__main__":
    main()
