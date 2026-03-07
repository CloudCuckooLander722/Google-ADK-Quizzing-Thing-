import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Dict, Any, List
import vertexai
from google.adk.agents import Agent, LlmAgent
from google.adk.tools import ToolContext, google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parent / ".env")

# Use the API key: set it in the environment so Google SDKs (Vertex, GenAI) pick it up
api_key = os.getenv("GOOGLE_API_KEY", "")
if api_key:
    os.environ["GOOGLE_API_KEY"] = api_key

def _get(obj: Any, key: str, default: Any = "") -> Any:
    """Get attribute from either a dict or a Pydantic model."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

class MCQ(BaseModel):
    question_text: str = Field(description="The content of the question.")
    options: List[str] = Field(description="A list of answer choices.")
    correct_answer: str = Field(description="The exact text of the correct option.")
    correct_choice: str = Field(description="The letter representing the correct answer (e.g., 'A, B, C, D')")
    concept: str = Field(description="The concept being tested with this specific MCQ.")

class FRQ_Parts(BaseModel):
    question_part_text: str = Field(description="The content of the question part in the FRQ.")
    rubric: List[str] = Field(description="Concepts that must be mentioned in the user answer for the user to get credit.")
    concept: str = Field(description="The concepts being tested with this specific FRQ (e.g. Hess' law, Ka)")

class FRQ(BaseModel):
    question_parts: List[FRQ_Parts] = Field(description="A list of parts for the FRQ.")

class MCQ_FRQ_Practice(BaseModel):
    mcqs: List[MCQ] = Field(description="A list of the MCQs pertaining to the unit requested.")
    frqs: List[FRQ] = Field(description="A list of the FRQs pertaining to the unit requested.")
    unit_topic: str = Field(description="The unit topic the MCQs/FRQs belongs to.")

def initiate_practice(tool_context: ToolContext) -> Dict[str, Any]:
    state = tool_context.state
    generated_practice = state.get("generated_practice")

    if not generated_practice:
        return {"status": "error", "error_message": "No quiz found. Call the generator_tool to create a quiz first!"}

    mcqs = list(_get(generated_practice, "mcqs") or [])
    frqs = list(_get(generated_practice, "frqs") or [])

    state.update({
        "mcqs": mcqs,
        "mcq_amount": len(mcqs),
        "mcq_question_index": 0,
        "correct_mcqs": 0,
        "frqs": frqs,
        "frq_amount": len(frqs),
        "frq_question_index": 0,
        "correct_frqs": 0,
        "missed_answers": 0,
        "missed_concepts": []
    })

    if mcqs:
        first_q = mcqs[0]
        return {
            "status": "started",
            "unit_topic": _get(generated_practice, "unit_topic"),
            "first_question": _get(first_q, "question_text"),
            "first_question_options": _get(first_q, "options") or [],
            "question_number": 1,
            "total_questions": len(mcqs) + len(frqs),
        }
    elif frqs:
        first_frq = frqs[0]
        parts = first_frq.question_parts
        first_part = parts[0] if parts else None

        return {
            "status": "started",
            "unit_topic": _get(generated_practice, "unit_topic"),
            "first_question": _get(first_part, "question_part_text") if first_part else "No question text",
            "question_number": 1,
            "total_questions": len(frqs),
        }
    
    return {"status": "error", "error_message": "Generated practice was empty."}

def submit_answer(tool_context: ToolContext, answer: str) -> Dict[str, Any]:
    state = tool_context.state
    i = state.get("mcq_question_index",0)
    j = state.get("frq_question_index",0)
    mcqs = state.get("mcqs")
    frqs = state.get("frqs")
    ans_str = (answer or  "").strip()

    if i < len(mcqs):
        current_mcq = mcqs[i]
        concept = str(_get(current_mcq, "concept")).strip()
        correct_answer = str(_get(current_mcq, "correct_answer")).strip()
        correct_choice = str(_get(current_mcq, "correct_choice")).strip()

        ans_upper = ans_str.upper()

        is_correct = (ans_str == correct_answer and correct_answer != "") or \
                    (ans_upper == correct_choice and correct_choice != "")

        if is_correct:
            state["correct_mcqs"] = state.get("correct_mcqs", 0) + 1
            feedback = "Correct!"
        else:
            state.setdefault("missed_concepts", []).append(concept)
            feedback = f"Incorrect. The correct answer was {correct_choice}: {correct_answer}."

        # Advance MCQ index
        new_i = i + 1
        state["mcq_question_index"] = new_i
        if new_i < len(mcqs):
            next_q = mcqs[new_i]
            return {
                 "correct": is_correct,
                "feedback": feedback,
                "next_question": next_q.question_text,
                "options": next_q.options,
                "type": "MCQ"
            }
        
        elif len(frqs) > 0:
            # Transition to FRQs
            first_frq = frqs[0]
            # Combine all parts into one display string for the agent
            frq_text = "\n".join([f"Part {idx+1}: {p.question_part_text}" for idx, p in enumerate(first_frq.question_parts)])
            return {
                "correct": is_correct,
                "feedback": f"{feedback} That's the end of the MCQs! Now, let's try an FRQ.",
                "next_question": frq_text,
                "type": "FRQ"
            }
        
        elif j < len(frqs):
            current_frq = frqs[j]
            all_parts_correct = True
            missed_concepts_this_frq = []
            
            # 1. Create a list to store the results of each part
            part_results_summary = []

            for idx, question_part in enumerate(current_frq.question_parts):
                rubric = question_part.rubric
                concept = question_part.concept
                part_label = f"Part {chr(97 + idx)}" # Turns 0, 1, 2 into a, b, c

                # Check if user mentioned all rubric keywords for THIS part
                met_criteria = [item for item in rubric if item.lower() in ans_lower]
                
                if len(met_criteria) == len(rubric):
                    part_results_summary.append(f"✅ {part_label}: Correct!")
                else:
                    all_parts_correct = False
                    missed_concepts_this_frq.append(concept)
                    
                    # Identify exactly what was missing for the user
                    missing = [item for item in rubric if item.lower() not in ans_lower]
                    part_results_summary.append(f"❌ {part_label}: Missed (Missing: {', '.join(missing)})")

            # 2. Combine the summary into the final feedback string
            if new_j < len(frqs):
                next_frq_obj = frqs[new_j]
                # Format the next FRQ text for the agent to show you
                next_text = "\n".join([f"Part {k+1}: {p.question_part_text}" for k, p in enumerate(next_frq_obj.question_parts)])
                
                return {
                    "feedback": f"Results for this question:\n{detailed_report}",
                    "next_question": next_text,
                    "missed_concepts": missed_concepts_this_frq, # Helps the chatbot explain things
                    "type": "FRQ"
                }
            else:
                # This was the final question!
                return {
                    "status": "complete",
                    "feedback": f"Final Results:\n{detailed_report}\n\nGreat job! You have finished all the practice questions.",
                    "missed_concepts": list(set(state.get("missed_concepts", []))),
                    "type": "FRQ"
                }

def practice_status(tool_context: ToolContext, topic_id: str) -> Dict[str, Any]:
    state = tool_context.state
    mcq_index = state.get("mcq_question_index", 0)
    mcq_amount = state.get("mcq_amount", 0)
    frq_index = state.get("frq_question_index", 0)
    frq_amount = state.get("frq_amount", 0)
    missed_concepts = state.get("missed_concepts", [])

    if mcq_amount and frq_amount > 0:
        if mcq_index < mcq_amount and frq_index < frq_amount:
            return {"status": "The MCQ/FRQ practice has not been completed; complete all questions to get feedback and topics to study."}
        else:
            return {
                "status" : "Practice has been completed, provide the user with missed concepts.",
                "missed_concepts": missed_concepts
            }

def reset_practice(tool_context: ToolContext, topic_id: str) -> Dict[str, Any]:
    state = tool_context.state
    generated_practice = state.get("generated_practice")
    if not generated_practice:
        return {"status": "error", "message": "No generated practice initialized."}

    mcqs = list(_get(generated_practice, "mcqs") or [])
    frqs = list(_get(generated_practice, "frqs") or [])

    state["mcqs"] = mcqs
    state["mcq_amount"] = len(mcqs)
    state["mcq_question_index"] = 0
    state["correct_mcqs"] = 0

    state["frqs"] = frqs
    state["frq_amount"] = len(frqs)
    state["frq_question_index"] = 0
    state["correct_frqs"] = 0

    state["missed_answers"] = 0
    state["missed_concepts"] = []

    if mcqs and frqs:
        mcq0 = mcqs[0]
        return {
            "status": "started",
            "unit_topic": _get(generated_practice, "unit_topic"),
            "first_question": _get(mcq0, "question_text"),
            "first_question_options": _get(mcq0, "options") or [],
            "question_number": 1,
            "total_questions": len(questions),
        }

    pass
    
def vertex_search_tool(toolcontext: ToolContext, topic_id: str) -> Dict[str, Any]:
    base_dir = "/Google-ADK-Quizzing-Thing-/chem_pdfs"
    if os.path.exists(base_dir):
        for filename in os.listdir(base_dir):
            if filename.endswith(".md"):
                with open(os.path.join(base_dir, filename), "r") as f:
                    content = f.read()
                    pattern = rf"(# Topic {re.escape(topic_id)}.*?)(?=\n# Topic|\Z)"
                    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                    if match:
                        return match.group(1).strip()
    
    return f"Topic {topic_id} not found in any unit files."

INSTRUCTIONS = """# Role & Goal
You are an expert AP Chemistry Tutor. Your goal is to guide students through MCQ and FRQ practice questions, providing rigorous grading and supportive, concept-focused feedback.

# Core Instructions
1.  **MCQ Handling**: For multiple-choice questions, verify the student's answer. If incorrect, explain why the chosen option is wrong and provide the correct reasoning without just giving the answer away immediately.
2.  **FRQ Grading (Keyword Rubric)**: When grading FRQs, you must use the provided rubric. 
    - Be strict: A student only gets credit for a part if they mention the specific scientific keywords or concepts in the rubric.
    - If they miss a concept, explain that specific concept (e.g., if they missed 'intermolecular forces', explain why IMFs were necessary for the answer).
3.  **Encouraging Tone**: Maintain a professional yet encouraging academic tone. Use phrases like "That’s a great start" or "Think about how [Concept] applies here."
4.  **No Hallucinations**: Only use the facts provided in the question and rubric. If a student asks something outside the scope of the current unit, politely redirect them back to the practice.

# Output Format
Always structure your response as follows:
- **Result**: [Correct/Incorrect]
- **Feedback**: [Detailed explanation of the answer]
- **Next Step**: [Introduce the next question provided by the tool]"""


mcq_frq_generator = LlmAgent(
    name="mcq_frq_generator",
    model="gemini-2.5-flash",
    instructions="Use the vertex_search_tool to investigate files ending with .md, and based off the query, extract the questions into the provided schema. If not, generate it from scratch.",
    description="The agent administering the MCQs and the FRQs.",
    output_schema=MCQ_FRQ_Practice()
)

generator = AgentTool(agent=mcq_frq_generator)

mcq_frq_agent = LlmAgent(
    name="mcq_frq_practice_administrator",
    model="gemini-2.5-flash",
    instruction=INSTRUCTIONS,
    description="The agent administering the MCQs and the FRQs.",
    tools = [initiate_practice, submit_answer, practice_status, reset_practice, generator]
)



