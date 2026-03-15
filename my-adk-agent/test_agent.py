"""
Unit tests for quiz agent tools (start_quiz, submit_answer, get_quiz_status, reset_quiz).
Uses a mock ToolContext so no FastAPI or agent_ui_adk is required.
"""
from quizzing_agent.agent import (
    start_quiz,
    submit_answer,
    get_quiz_status,
    reset_quiz,
)


class MockToolContext:
    def __init__(self):
        self.state = {}


def test_start_quiz_no_generated_quiz():
    ctx = MockToolContext()
    out = start_quiz(ctx)
    assert out["status"] == "error"
    assert "generator_tool" in out["error_message"]


def test_start_quiz_success():
    ctx = MockToolContext()
    ctx.state["generated_quiz"] = {
        "quiz_title": "Unit 6 Quiz",
        "questions": [
            {
                "question_text": "What is delta H?",
                "options": ["A) Enthalpy", "B) Entropy", "C) Energy", "D) Heat"],
                "correct_answer": "A) Enthalpy",
                "correct_choice": "A",
                "explanation": "Delta H is enthalpy.",
                "concept": "Enthalpy",
            },
            {
                "question_text": "What is delta S?",
                "options": ["A) Enthalpy", "B) Entropy", "C) Energy", "D) Heat"],
                "correct_answer": "B) Entropy",
                "correct_choice": "B",
                "explanation": "Delta S is entropy.",
                "concept": "Entropy",
            },
        ],
    }
    out = start_quiz(ctx)
    assert out["status"] == "started"
    assert "delta H" in out["first_question"]
    assert out["total_questions"] == 2
    assert ctx.state["current_question_index"] == 0
    assert ctx.state["quiz_questions"] is not None


def test_submit_answer_correct_by_letter():
    ctx = MockToolContext()
    ctx.state["quiz_questions"] = [
        {
            "question_text": "Q1",
            "options": ["A) X", "B) Y", "C) Z", "D) W"],
            "correct_answer": "B) Y",
            "correct_choice": "B",
            "explanation": "Because Y.",
            "concept": "Concept1",
        },
        {
            "question_text": "Q2",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "C",
            "correct_choice": "C",
            "explanation": "C is right.",
            "concept": "Concept2",
        },
    ]
    ctx.state["current_question_index"] = 0
    ctx.state["total_questions"] = 2
    ctx.state["total_answered"] = 0
    ctx.state["correct_answers"] = 0

    out = submit_answer(ctx, "B")
    assert out["correct"] is True
    assert "next_question" in out
    assert out["next_question"] == "Q2"
    assert out.get("quiz_complete") is not True
    assert ctx.state["current_question_index"] == 1
    assert ctx.state["correct_answers"] == 1


def test_submit_answer_wrong_then_next():
    ctx = MockToolContext()
    ctx.state["quiz_questions"] = [
        {"question_text": "Q1", "options": ["A", "B", "C", "D"], "correct_answer": "A", "correct_choice": "A", "explanation": "A", "concept": "C1"},
        {"question_text": "Q2", "options": ["A", "B", "C", "D"], "correct_answer": "B", "correct_choice": "B", "explanation": "B", "concept": "C2"},
    ]
    ctx.state["current_question_index"] = 0
    ctx.state["total_questions"] = 2
    ctx.state["total_answered"] = 0
    ctx.state["correct_answers"] = 0

    out = submit_answer(ctx, "B")  # wrong, correct is A
    assert out["correct"] is False
    assert "Wrong" in out["feedback"]
    assert out["next_question"] == "Q2"
    assert ctx.state["missed_concepts"] == ["C1"]


def test_submit_answer_last_question_quiz_complete():
    ctx = MockToolContext()
    ctx.state["quiz_questions"] = [
        {"question_text": "Q1", "options": ["A", "B"], "correct_answer": "A", "correct_choice": "A", "explanation": "A", "concept": "C1"},
    ]
    ctx.state["current_question_index"] = 0
    ctx.state["total_questions"] = 1
    ctx.state["total_answered"] = 0
    ctx.state["correct_answers"] = 0

    out = submit_answer(ctx, "A")
    assert out["correct"] is True
    assert out.get("quiz_complete") is True
    assert out["next_question"] is None


def test_submit_answer_correct_lowercase_letter():
    """Single-letter answer 'a' should match correct_choice 'A'."""
    ctx = MockToolContext()
    ctx.state["quiz_questions"] = [
        {"question_text": "Q1", "options": ["A", "B"], "correct_answer": "A", "correct_choice": "A", "explanation": "A", "concept": "C1"},
    ]
    ctx.state["current_question_index"] = 0
    ctx.state["total_questions"] = 1
    ctx.state["total_answered"] = 0
    ctx.state["correct_answers"] = 0
    out = submit_answer(ctx, "a")
    assert out["correct"] is True


def test_submit_answer_no_questions():
    ctx = MockToolContext()
    ctx.state["quiz_questions"] = []
    ctx.state["current_question_index"] = 0
    out = submit_answer(ctx, "A")
    assert "error" in out


def test_submit_answer_none_treated_as_wrong():
    """None or empty answer should not crash; treated as wrong."""
    ctx = MockToolContext()
    ctx.state["quiz_questions"] = [
        {"question_text": "Q1", "options": ["A", "B"], "correct_answer": "A", "correct_choice": "A", "explanation": "A", "concept": "C1"},
    ]
    ctx.state["current_question_index"] = 0
    ctx.state["total_questions"] = 1
    ctx.state["total_answered"] = 0
    ctx.state["correct_answers"] = 0
    out = submit_answer(ctx, None)
    assert out["correct"] is False
    assert "Wrong" in out["feedback"]


def test_get_quiz_status():
    ctx = MockToolContext()
    ctx.state["total_answered"] = 1
    ctx.state["total_questions"] = 3
    ctx.state["correct_answers"] = 1
    ctx.state["current_question_index"] = 1
    out = get_quiz_status(ctx)
    assert out["answered"] == 1
    assert "100.00%" in out["score_so_far"]
    assert out["is_quiz_finished"] is False


def test_get_quiz_status_finished():
    ctx = MockToolContext()
    ctx.state["total_answered"] = 2
    ctx.state["total_questions"] = 2
    ctx.state["correct_answers"] = 2
    ctx.state["current_question_index"] = 2
    out = get_quiz_status(ctx)
    assert out["is_quiz_finished"] is True
    assert "next_steps" in out


def test_reset_quiz_no_quiz():
    ctx = MockToolContext()
    out = reset_quiz(ctx)
    assert out["status"] == "error"


def test_reset_quiz_success():
    ctx = MockToolContext()
    ctx.state["generated_quiz"] = {
        "quiz_title": "Quiz",
        "questions": [
            {"question_text": "First?", "options": ["A", "B"], "correct_answer": "A", "correct_choice": "A", "explanation": "A", "concept": "C1"},
        ],
    }
    ctx.state["quiz_questions"] = []
    ctx.state["current_question_index"] = 5
    ctx.state["missed_concepts"] = ["old"]
    out = reset_quiz(ctx)
    assert out["status"] == "reset_success"
    assert out["first_question"] == "First?"
    assert ctx.state["current_question_index"] == 0
    assert ctx.state["missed_concepts"] == []
    assert len(ctx.state["quiz_questions"]) == 1


def run_all():
    tests = [
        test_start_quiz_no_generated_quiz,
        test_start_quiz_success,
        test_submit_answer_correct_by_letter,
        test_submit_answer_correct_lowercase_letter,
        test_submit_answer_wrong_then_next,
        test_submit_answer_last_question_quiz_complete,
        test_submit_answer_no_questions,
        test_submit_answer_none_treated_as_wrong,
        test_get_quiz_status,
        test_get_quiz_status_finished,
        test_reset_quiz_no_quiz,
        test_reset_quiz_success,
    ]
    failed = []
    for t in tests:
        try:
            t()
            print(f"  OK  {t.__name__}")
        except Exception as e:
            print(f"  FAIL {t.__name__}: {e}")
            failed.append((t.__name__, e))
    if failed:
        print(f"\n{len(failed)} failed")
        raise SystemExit(1)
    print(f"\nAll {len(tests)} tests passed.")


if __name__ == "__main__":
    run_all()
