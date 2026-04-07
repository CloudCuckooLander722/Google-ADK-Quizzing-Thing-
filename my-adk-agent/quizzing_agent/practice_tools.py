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
from pydantic import BaseModel, Field, model_validator
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.genai import types

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
    #new line: points -> is len(rubric) legit? (4/1/26)
    points: int = Field(description="The number of points awarded in this question based on concepts mentioned in the rubric (e.g. 1 point awarded for mentioning microstates) ")
    concept: str = Field(description="The concepts being tested with this specific FRQ (e.g. Hess' law, Ka)")

    @model_validator(mode="after")
    def set_points_from_rubric(self) -> 'FRQ_Parts':
        self.points = len(self.rubric)
        return self

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
    #pay attention to this line: new change
    frqs_points = sum(points for frq in generated_practice.frqs for points in frq_question_parts.points)
    mcqs_points = len(mcqs)

    state.update({
        "mcqs": mcqs,
        "mcq_amount": len(mcqs),
        "mcq_question_index": 0,
        "correct_mcqs": 0,
        "mcq_points": mcqs_points,
        "frqs": frqs,
        "frq_amount": len(frqs),
        "frq_question_index": 0,
        "frqs_points": frqs_points,
        #new line for frqs_points (4/1/26)
        "frqs_points_awarded": 0, 
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
    frq_points_awarded = state.get("frq_points_awarded", 0) #new variable (4/1/26): frq_points_awarded
    
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
            first_frq = frqs[0] #new line (4/1/26)
            frq_text = "\n".join([f"Part {idx+1}: {p.question_part_text}" for idx, p in enumerate(first_frq.question_parts)])
            return {
                "correct": is_correct,
                "feedback": f"{feedback} That's the end of the MCQs! Now, let's try an FRQ.",
                "next_question": frq_text,
                "type": "FRQ"
            }
        
    elif j < len(frqs):
            current_frq = frqs[j]
            ans_lower = ans_str.lower()
            missed_concepts_this_frq = []
            part_results_summary = []
            detailed_scoring_lines = []
            all_parts_correct = True #we've got to define a variable which stores the amount of points the user won (4/1/26)
            all_rubrics = [] #so we ca add all of the rubrics

            for idx, question_part in enumerate(current_frq.question_parts):
                rubric = question_part.rubric
                part_label = f"Part {chr(97 + idx)}"

                missing = [item for item in rubric if item.lower() not in ans_lower]
                met_criteria = [item for item in rubric if item.lower() in ans_lower]
                
                if len(met_criteria) == len(rubric):
                    part_results_summary.append(f"✅ {part_label}: Correct!")
                else:
                    all_parts_correct = False
                    part_results_summary.append(f"❌ {part_label}: Missed (Missing: {', '.join(missing)})")
                    missed_concepts_this_frq.extend(missing)
                
                all_rubrics.append({part_label: question_part.rubric})
                
                points_awarded = len(met_criteria)
                frq_points_awarded = state.get("frq_points_awarded", 0)

                frq_points_awarded += points_awarded
                state["frq_points_awarded"] = frq_points_awarded

                met_str = ", ".join(met_criteria) if met_criteria else "None"
                detailed_scoring_lines.append(f"{part_label}: {points_awarded}/{len(rubric)} pts (Concepts: {met_str})")

            summary_text = "\n".join(part_results_summary)
            score_text = "\nScoring Details:\n" + "\n".join(detailed_scoring_lines) if frq_grading_enabled == "y" else ""
            full_feedback = f"{summary_text}\n{score_text}"
            new_j = j + 1
            state["frq_question_index"] = new_j 
            #how to display what I did wrong before I make the defailed report?
            state.setdefault("missed_concepts", []).extend(missed_concepts_this_frq)
            if new_j < len(frqs):
                next_frq_obj = frqs[new_j]
                # Format the next FRQ text for the agent to show you
                next_text = "\n".join([f"Part {k+1}: {p.question_part_text}" for k, p in enumerate(next_frq_obj.question_parts)])
                
                return {
                    "feedback": f"Results for this question:\n{full_feedback}",
                    "rubric": all_rubrics, #new edit (4/3/26)
                    "next_question": next_text,
                    "missed_concepts": missed_concepts_this_frq, # Helps the chatbot explain things
                    "type": "FRQ"
                }
            else:
                final_points = state.get("frq_points_awarded", 0)

                return {
                    "status": "complete",
                    "feedback": f"Final Results:\n{full_feedback}\n\nGreat job! You have finished all the practice questions.",
                    "missed_concepts": list(set(state.get("missed_concepts", []))),
                    "type": "FRQ"
                }

def format_score(earned, total):
    if not total or total <= 0:
        return "N/A (No points assigned)"
    percentage = (earned / total) * 100
    return f"{earned}/{total} ({percentage:.1f}%)"

def practice_status(tool_context: ToolContext, topic_id: str, grading_enabled: str) -> Dict[str, Any]:
    """
    Checks the status of MCQ and FRQ practice.
    
    Args:
        topic_id: The ID of the topic being practiced.
        grading_enabled: Set to 'y' to calculate and return scores, or 'n' to skip grading.
    """
    state = tool_context.state
    mcq_index = state.get("mcq_question_index", 0)
    mcq_amount = state.get("mcq_amount", 0)
    frq_index = state.get("frq_question_index", 0)
    frq_amount = state.get("frq_amount", 0)
    missed_concepts = state.get("missed_concepts", [])

    correct_mcqs = state.get("correct_mcqs", 0)
    mcq_points = state.get("mcq_points", 0) 
    
    frq_points_awarded = state.get("frqs_points_awarded", 0)
    frq_points = state.get("frqs_points", 0)


    if mcq_amount and frq_amount > 0:
        if mcq_index < mcq_amount and frq_index < frq_amount:
            return {"status": "The MCQ/FRQ practice has not been completed; complete all questions to get feedback and topics to study."}
        else:
            return {
                "status" : "Practice has been completed, provide the user with missed concepts.",
                "missed_concepts": missed_concepts
            }

            if grading_enabled == "y":
                mcq_score = format_score(correct_mcqs, mcq_points)
                frq_score = format_score(frq_points_awarded, frq_points)
                #how to make my code more robust instead of crashing?
                return {
                "status" : "Practice has been completed, provide the user with missed concepts.",
                "missed_concepts": missed_concepts,
                "mcq_score": mcq_score,
                "frq_score": frq_score
                
            }

def reset_practice(tool_context: ToolContext, topic_id: str) -> Dict[str, Any]:
    state = tool_context.state
    generated_practice = state.get("generated_practice")
    if not generated_practice:
        return {"status": "error", "message": "No generated practice initialized."}

    mcqs = list(_get(generated_practice, "mcqs") or [])
    frqs = list(_get(generated_practice, "frqs") or [])

    frqs_points = sum(points for points in frq.question_parts.points for frq in generated_practice.frqs)

    mcqs_points = len(mcqs)

    state.update({
        "mcqs": mcqs,
        "mcq_amount": len(mcqs),
        "mcq_question_index": 0,
        "mcqs_points": mcqs_points,
        "correct_mcqs": 0,
        "frqs": frqs,
        "frq_amount": len(frqs),
        "frq_question_index": 0,
        "frqs_points": frqs_points,
        
        #new line for frqs_points (4/1/26)
        "frqs_points_awarded": 0, 
        "correct_frqs": 0,
        "missed_answers": 0,
        "missed_concepts": []
    })
 #reset frq_points_awarded
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
    
def vertex_search_tool(tool_context: ToolContext, topic_id: str) -> Dict[str, Any]:
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

search_tool = GoogleSearchTool(bypass_multi_tools_limit=True)

search_agent = LlmAgent(
    name="search_agent",
    model="gemini-2.0-flash", # Use 2.0-flash (stable for search)
    instruction="""
    # OBJECTIVE
    You are a precision-guided search agent for AP Chemistry. Your task is to retrieve MCQs and FRQs that match the EXACT requested Topic ID.

    # STEP 1: THE SYLLABUS BARRICADE (Reference Map)
    Use this map to identify the 'Core Concept' before searching:
    - UNIT 1 (Atomic Structure): 1.1 Moles/Molar Mass, 1.2 Mass Spec, 1.3 Elemental Comp, 1.4 Mixtures, 1.5 Atomic Structure/Electron Config, 1.6 PES, 1.7 Periodic Trends, 1.8 Valence/Ionic Compounds.
    - UNIT 2 (Bonding): 2.1 Chemical Bonds, 2.2 Intramolecular Force, 2.3 Ionic Solids, 2.4 Metals/Alloys, 2.5 Lewis Diagrams, 2.6 Resonance/Formal Charge, 2.7 VSEPR/Hybridization.
    - UNIT 3 (IMFs/Gases): 3.1 IMFs, 3.2 Solids, 3.3 Solids/Liquids/Gases, 3.4 Ideal Gas Law, 3.5 KMT, 3.6 Deviations (Non-Ideal), 3.7 Solutions/Mixtures, 3.8 Representations of Solutions, 3.9 Separations, 3.10 Solubility, 3.11 Spectroscopy/PES, 3.12 Photoelectric Effect, 3.13 Beer-Lambert Law.
    - UNIT 4 (Reactions): 4.1 Intro to Reactions, 4.2 Net Ionic Eqs, 4.3 Reps of Reactions, 4.4 Physical/Chemical Changes, 4.5 Stoichiometry, 4.6 Titrations, 4.7 Types of Reactions, 4.8 Acid-Base Reactions, 4.9 Redox.
    - UNIT 5 (Kinetics): 5.1 Reaction Rates, 5.2 Rate Law Intro, 5.3 Concentration Changes, 5.4 Elementary Reactions, 5.5 Collision Model, 5.6 Reaction Energy Profile, 5.7 mechanisms, 5.8-5.9 Rate Laws/Steady State, 5.10 Multistep Mechanisms, 5.11 Catalysis.
    - UNIT 6 (Thermodynamics): 6.1 Endothermic/Exothermic, 6.2 Energy Diagrams, 6.3 Thermal Equilibrium, 6.4 Heat Capacity/Calorimetry, 6.5 Energy of Phase Changes, 6.6 Intro to Enthalpy of Reaction, 6.7 Bond Enthalpies, 6.8 Enthalpy of Formation, 6.9 Hess's Law.
    - UNIT 7 (Equilibrium): 7.1 Intro to Equilibrium, 7.2 Direction of Reversible Rxns, 7.3 Q vs K, 7.4 Eq Constant Properties, 7.5 Calculating K, 7.6 Magnitude of K, 7.7 Le Chatelier’s, 7.8 Intro to Solubility Eq (Ksp), 7.9 Common-Ion Effect, 7.10 pH and Solubility, 7.11 Free Energy of Dissolution.
    - UNIT 8 (Acids/Bases): 8.1 pH/pOH, 8.2 Weak Acids/Bases, 8.3 Titrations (Acid-Base), 8.4 Molecular Structure of Acids, 8.5 pH/pKa, 8.6 Properties of Buffers, 8.7 Henderson-Hasselbalch, 8.8 Buffer Capacity, 8.9 Titration Curves (Weak Acids/Bases), 8.10 pKa and Indicators.
    - UNIT 9 (Thermo & Electro): 9.1 Intro to Entropy, 9.2 Absolute Entropy/Change, 9.3 Gibbs Free Energy, 9.4 Thermodynamic/Kinetic Control, 9.5 Free Energy/Equilibrium, 9.6 Coupled Reactions, 9.7 Galvanic (Voltaic) and Electrolytic Cells, 9.8 Cell Potential, 9.9 Cell Potential Under Nonstandard Conditions, 9.10 Electrolysis/Faraday's Law.

    # STEP 2: SEARCH QUERY GENERATION
    1. Translate Topic ID (e.g., 9.1) to its title (e.g., 'Intro to Entropy').
    2. Format queries: "AP Chemistry [Topic Name] MCQ" and "AP Chem [Topic Name] FRQ".
    3. NEGATIVE RESTRAINT: For 9.1-9.6, append '-voltaic -anode -cathode -potential' to exclude Electrochemistry drift.

    # STEP 3: FILTERING
    Before returning text, verify the snippet contains the 'Core Concept' keywords. If searching 9.1 and results mention 'Voltage' or 'Battery', DISCARD and retry.

    # OUTPUT
    Return the high-fidelity raw text from the filtered results.
    """,
    tools=[search_tool]
)

mcq_frq_generator = LlmAgent(
    name="mcq_frq_generator",
    model="gemini-2.5-pro", # Note: use 2.0-flash unless 2.5 is actually out
    instruction="""
    # OBJECTIVE
    Generate AP Chemistry questions that mimic the official College Board difficulty and 'tricky' wording.

    # STEP 1: RESEARCH
    Call 'search_agent' to find actual released AP Chem questions for the topic. Use the released AP Chem MCQs/FRQs, but if you can't find any on the topic, Use these as a template for style and complexity. In addition, find related articles to the topic as a means of background research.

    # STEP 2: QUESTION DESIGN RULES
    - **No Simple Recall**: Do not ask for definitions. Ask how a change in one variable (e.g., Temperature) affects a result (e.g., Keq or Voltage).
    - **Distractor Logic**: Create 'attractive distractors' based on common student misconceptions (e.g., forgetting to convert Celsius to Kelvin, or flipping the sign of ΔG).
    - **Context-Heavy**: Every FRQ must start with a 'Scenario' (e.g., "A student performs a titration...") or a set of data/table.
    - **Wording**: Use standard AP phrases like "Justify your answer in terms of intermolecular forces," "Which of the following best explains," or "In a particulate representation..."

    # STEP 3: OUTPUT
    Extract or generate the EXACT number of MCQs and FRQs requested into the provided schema. If search fails, synthesize questions based on the current Course and Exam Description (CED).
    """,
    description="The agent generating structured MCQs and FRQs.",
    output_schema=MCQ_FRQ_Practice,
    tools=[AgentTool(agent=search_agent), vertex_search_tool],
    generate_content_config=types.GenerateContentConfig(
        temperature=0.2, # More deterministic output
        max_output_tokens=8192
    ),
    output_key="generated_practice"
)

question_generator = AgentTool(agent=mcq_frq_generator)

mcq_frq_agent = LlmAgent(
    name="mcq_frq_practice_administrator",
    model="gemini-2.5-flash",
    instruction=INSTRUCTIONS,
    description="The agent administering the MCQs and the FRQs.",
    tools = [initiate_practice, submit_answer, practice_status, reset_practice, question_generator]
)



