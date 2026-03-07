from practice_tools import *
import asyncio
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
from vertexai import Client
from google.adk.memory import VertexAiMemoryBankService
from google.adk.sessions import VertexAiSessionService
from google.adk.runners import Runner
from google.genai import types

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/minh/Google-ADK-Quizzing-Thing-/gen-lang-client-0565764733-65a9f8d91a7c.json"


project_id = os.environ.get("GCP_PROJECT_ID")
client = Client(
    project=project_id,
    location="us-central1",
)

memory_tool = PreloadMemoryTool()

agent_engine = client.agent_engines.create()
agent_engine_id = agent_engine.api_resource.name.split("/")[-1]
app_name = "your-app-name"


APP_NAME = f"projects/{project_id}/locations/us-central1/reasoningEngines/{agent_engine_id}"
USER_ID = "cloud_cuckoo"

memory_service = VertexAiMemoryBankService(
    project=project_id,
    location="us-central1",
    agent_engine_id=agent_engine_id
)

session_service = VertexAiSessionService(
    project=project_id,
    location="us-central1",
    agent_engine_id=agent_engine_id
)

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


async def setup_session_and_runner():
    session = await session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
    runner = Runner(agent=mcq_frq_agent, 
                    app_name=APP_NAME, 
                    session_service=session_service, 
                    memory_service=memory_service,
                    )
    
    return session, runner

async def run_single_turn(query, session, user_id, runner):
        """Run a single conversation turn."""
        content = types.Content(role="user", parts=[types.Part(text=query)])
        events = runner.run_async(user_id=user_id, session_id=session.id, new_message=content)

        response_content = None
        async for event in events:
            if event.is_final_response():
                response_content = event.content.parts[0].text
                
        return response_content


async def chat_loop(session, user_id, runner) -> None:
            """Main chat interface loop."""
            print("\nStarting chat. Type 'exit' or 'quit' to end.")
            print("Every message will be automatically stored in memory.\n")
        
            while True:
                user_input = input("\nYou: ")
                if user_input.lower() in ["quit", "exit", "bye"]:
                    print("\nAssistant: Thank you for chatting. Have a great day!")
                    break
        
                response = await run_single_turn(user_input, session, user_id, runner=runner)
                if response:
                    print(f"\nAssistant: {response}")
        
            completed_session = await runner.session_service.get_session(app_name=app_name, user_id=USER_ID, session_id=session.id)
            
            await memory_service.add_session_to_memory(completed_session)

def run_session():

    session, runner = asyncio.run(setup_session_and_runner())

    asyncio.run(chat_loop(session=session, user_id=USER_ID, runner=runner))

print("hello world")
run_session()

