import os
from pathlib import Path
from dotenv import load_dotenv
# Load .env from the same folder as this script (works no matter where you run from)
load_dotenv(Path(__file__).resolve().parent / ".env")

# Use the API key: set it in the environment so Google SDKs (Vertex, GenAI) pick it up
api_key = os.getenv("GOOGLE_API_KEY", "")
if api_key:
    os.environ["GOOGLE_API_KEY"] = api_key

from google.adk.agents import Agent, LlmAgent
from google.adk.tools import ToolContext, google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from pydantic import BaseModel, Field
from typing import Dict, Any, List
import vertexai
from practice_tools import MCQ_FRQ_Practice, mcq_frq_generator, mcq_frq_agent

print("✅ ADK components imported successfully.")

class QuizQuestion(BaseModel):
    question_text: str = Field(description="The actual question content.")
    options: List[str] = Field(description="A list of 4 multiple-choice options.")
    correct_answer: str = Field(description="The exact text of the correct option.")
    explanation: str = Field(description="Rationale for the correct answer, tying to the concepts related to this question.")
    concept: str = Field(description="The underlying concept being quizzed.")
    correct_choice: str = Field(description="The letter representing the correct answer (e.g., 'A, B, C, D')")

class GeneratedQuiz(BaseModel):
    quiz_title: str = Field(description="Title of the quiz (e.g., 'AP Chem Unit 6 Quiz')")
    questions: List[QuizQuestion] = Field(description="A list of question objects.")

def _get(obj: Any, key: str, default: Any = "") -> Any:
    """Get attribute from either a dict or a Pydantic model."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


QUIZ_INSTRUCTIONS = """
You are the AP Chemistry Quiz Master. You MUST use tools to progress.

STRICT OPERATIONAL HIERARCHY:
1. **Identify**: If you don't know the user's name, ask. Memories are preloaded each turn; use them when relevant.
2. **Generate**: If the user asks for a quiz, you MUST:
   - Call `generator_tool` (with the specific AP Chem Unit/Topic) to create the quiz and save it to `generated_quiz`.
   - DO NOT tell the user you are "finding" them; just execute the tool.
3. **Initialize**: Once questions are found, call `start_quiz()`.
   - Display the `first_question` text and `first_question_options` (A, B, C, D).
4. **Evaluate**: When the user provides an answer:
   - You MUST call `submit_answer(answer="user_input")`.
   - Provide the explanation/rationale for the answer.
   - IMMEDIATELY show the next question. DO NOT ask "Ready for the next one?"; just show it.
5. **Memory**: If a user gets a question wrong, the `submit_answer` tool logs the concept.
6. **Conclude**: When `get_quiz_status` indicates all questions are answered, show the score and call it a day.
7. **Search Concepts**: If the user asks for concepts they missed, use the preloaded memory (memory_tool surfaces it automatically).
CRITICAL RULES:
- Never say "I can't generate a quiz." If you lack questions, call `generator_tool`.
- Never give second chances on a question. One answer, one `submit_answer` call, move on.
"""

def start_quiz(tool_context: ToolContext,) -> Dict[str, Any]:
    state = tool_context.state
    
    quiz_data = state.get("generated_quiz")

    if not quiz_data:
        return {"status": "error", "error_message": "No quiz found. Call the generator_tool to create a quiz first!"}

    questions = list(_get(quiz_data, "questions") or [])

    state["quiz_questions"] = questions
    state["quiz_started"] = True
    state["current_question_index"] = 0
    state["correct_answers"] = 0
    state["total_answered"] = 0
    state["score_percentage"] = 0
    state["total_questions"] = len(questions)
    state["missed_questions"] = []
    state["missed_concepts"] = []

    if questions:
        q0 = questions[0]
        return {
            "status": "started",
            "quiz_title": _get(quiz_data, "quiz_title"),
            "first_question": _get(q0, "question_text"),
            "first_question_options": _get(q0, "options") or [],
            "question_number": 1,
            "total_questions": len(questions),
        }
        
    return {"status": "error", "error_message": "No questions available"}

def submit_answer(tool_context: ToolContext, answer: str) -> Dict[str, Any]:
    state = tool_context.state
    i = state.get("current_question_index", 0)
    questions = state.get("quiz_questions", [])
    if not questions or i >= len(questions):
        return {"error": "No active question found or quiz finished."}

    ans = (answer if answer is not None else "").strip()

    # Get the specific question object (dict or Pydantic)
    current_q = questions[i]
    correct_answer = str(_get(current_q, "correct_answer")).strip()
    correct_choice = str(_get(current_q, "correct_choice")).strip()

    # Normalize single-letter answers (A-D) so "a" matches "A"
    ans_letter = ans.upper() if len(ans) <= 2 else ans
    choice_letter = correct_choice.upper() if correct_choice and len(correct_choice) <= 2 else correct_choice

    is_correct = (ans == correct_answer and correct_answer != "") or \
                 (ans_letter == choice_letter and choice_letter != "")

    state["total_answered"] = state.get("total_answered", 0) + 1
    explanation = _get(current_q, "explanation", "No explanation provided")
    concept = _get(current_q, "concept", "General")

    if is_correct:
        state["correct_answers"] = state.get("correct_answers", 0) + 1
    else:
        state.setdefault("missed_questions", []).append(_get(current_q, "question_text"))
        state.setdefault("missed_concepts", []).append(concept)

    state['current_question_index'] = i + 1

    next_index = i + 1
    result = {
        "correct": is_correct,
        "feedback": "Correct!" if is_correct else f"Wrong. The answer was {correct_answer}",
        "explanation": explanation,
        "concept": concept,
    }
    if next_index < len(questions):
        next_q = questions[next_index]
        result["next_question"] = _get(next_q, "question_text")
        result["next_question_options"] = _get(next_q, "options") or []
        result["question_number"] = next_index + 1
        result["total_questions"] = len(questions)
    else:
        result["quiz_complete"] = True
        result["next_question"] = None
        result["next_question_options"] = []

    return result


def get_quiz_status(tool_context: ToolContext) -> Dict[str, Any]:
    state = tool_context.state
    
    # 1. Use .get(key, 0) to avoid NoneType errors
    answered = state.get('total_answered', 0)
    total = state.get('total_questions', 0)
    correct = state.get("correct_answers", 0)
    current_idx = state.get("current_question_index", 0)

    # 2. Check for zero to prevent crash
    score = (correct / answered) if answered > 0 else 0
    
    # 3. Determine if we should trigger the Vector DB archive
    is_finished = (answered >= total) and total > 0
    if total == 0:
        progress_text = "No quiz in progress"
    else:
        display_num = min(current_idx + 1, total)
        progress_text = "Quiz complete" if is_finished else f"Question {display_num} of {total}"

    response = {
        "current_progress": progress_text,
        "score_so_far": f"{score:.2%}",
        "answered": answered,
        "is_quiz_finished": is_finished
    }

    # 4. If finished, add a hint for the agent to archive missed concepts
    if is_finished:
        response["next_steps"] = "The quiz is over. I will now archive your missed concepts to your long-term memory."
        
    return response

def reset_quiz(tool_context: ToolContext) -> Dict[str, Any]:
    state = tool_context.state
    
    # 1. Retrieve quiz data safely
    quiz_data = state.get("generated_quiz")
    if not quiz_data:
        return {"status": "error", "message": "No quiz exists to reset."}

    questions = quiz_data.questions if isinstance(quiz_data, GeneratedQuiz) else _get(quiz_data, "questions") or []
    questions = list(questions)
    
    # 2. FULL RESET of the session state
    # Critical for accurate Vector Database archiving
    state["quiz_questions"] = list(questions)
    state["quiz_started"] = True
    state["current_question_index"] = 0
    state["correct_answers"] = 0
    state["total_answered"] = 0
    state["missed_questions"] = [] # MUST reset this
    state["missed_concepts"] = []  # MUST reset this
    state["total_questions"] = len(questions)
    
    # 3. Synchronize with Vertex AI Session Service
    # (Optional but recommended to force a state sync)
    
    if questions:
        first_q = questions[0]
        q_text = _get(first_q, "question_text")

        return {
            "status": "reset_success",
            "message": "The quiz has been reset. Here is your first question.",
            "first_question": q_text,
            "total_questions": len(questions) # Fixed the typo here
        }
    return {"status": "error", "message": "The stored quiz contains no questions."}


memory_tool = PreloadMemoryTool()
# API keys and config from .env (e.g. GOOGLE_API_KEY, GOOGLE_CLOUD_PROJECT)
project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "")
if project_id:
    _vertex_client = vertexai.Client(project=project_id, location="us-central1")
# (Vertex client/agent_engine can be used here for session/memory if needed.)

generator_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='generator_agent',
    instruction="Based off user prompt, search up relevant concepts and problems. Create a set of problems for a quiz and express them in JSON format.",
    output_schema=GeneratedQuiz,
    output_key="generated_quiz",
    
)

generator_tool = AgentTool(agent=generator_agent)

mcq_frq_generator_tool = AgentTool(agent=mcq_frq_generator)

conceptual_agent = Agent(
    name="quiz_master",
    model='gemini-2.5-flash',
    instruction=QUIZ_INSTRUCTIONS,
    description="The agent that manages the quizzing process.",
    tools=[start_quiz, submit_answer, get_quiz_status, reset_quiz, generator_tool],
    
)

ROOT_INSTRUCTIONS = """
# ROLE
You are the AP Chemistry Practice Coordinator. Your goal is to guide students to the most effective learning mode based on their needs.

# WORKFLOW
1. **Topic Identification**: Determine which AP Chemistry topic (e.g., Topic 8.7: pH and pKa) the user wants to study. If they are vague, ask clarifying questions.
2. **Mode Selection**: 
   - If the user wants structured practice (MCQs or FRQs), generate the materials using the 'mcq_frq_generator' tool, then transfer control to the 'mcq_frq_practice_administrator'.
   - If the user wants to explore a topic deeply or needs a concept explained via dialogue, transfer control to the 'conceptual_quizzing_agent'.
3. **Session Handoff**: When transferring, briefly summarize what you've prepared (e.g., "I've generated a quiz on Topic 8.7 for you. Handing you over to the proctor now.")

# PEDAGOGICAL GUIDELINES
- Focus on learning, not just correctness. 
- Ensure that the session state is initialized before handing over to sub-agents.
- If a sub-agent returns control to you, ask the student if they would like to switch topics or try a different practice mode.

Use code with caution.

🛠️ Key points:
The agent is instructed to transfer control rather than doing the work itself.
The mcq_frq_generator runs before the handoff.
The agent prioritizes topic understanding.
⚠️ Important:
Ensure the mcq_frq_agent description is distinct.
Bad Description: "An agent for questions."
Good Description: "Specialist for administering Multiple Choice (MCQ) and Free Response (FRQ) questions. Transfer here only after quiz data is generated."
"""

root_agent = Agent(
    name="master_agent",
    model="gemini-2.0-flash", 
    description="The primary entry point for AP Chemistry study. Routes students to MCQ/FRQ practice or conceptual deep-dives.",
    instruction=ROOT_INSTRUCTIONS,
    sub_agents=[conceptual_agent, mcq_frq_agent],
    tools=[generator_tool, mcq_frq_generator_tool, memory_tool],
    
)



