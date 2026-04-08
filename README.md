# Google-ADK-Quizzing-Thing-

Problem Statement: Create an application implementing Google-ADK modules and agents to generate MCQ and FRQ practice problems for AP Chem. 

Requirements (Backend):

1.1 - Based on the users' search query, the program will generate the specific quota of MCQs and FRQs. Agents are assigned Python functions and Pydantic fields to store, award points, and provide feedback for the questions researched or generated.

1.2 - The system shall monitor the total token count for every outgoing request. If a request exceeds 8,192 tokens, the system shall truncate the oldest questions in the chat history until the token count is less than 7000 tokens. 
(epicvstuff)

1.3.1 - Retrieval Logic:
Upon receiving a practice request, the system shall branch based on question type:
MCQ Path: Invoke vertex_search_tool to perform a semantic search against the indexed "AP Chem MCQ Packets" data store.
FRQ Path: Invoke search_agent (Web Search) to retrieve official College Board released FRQs and their corresponding scoring guidelines.
(epicvstuff)

1.3.2 - RAG Answer Key Formulation:
The system shall implement a Retriever-Augmented Generation (RAG) chain. It must inject the retrieved source text (scoring rubrics or textbook excerpts) into the LLM context window as "Reference Material." The LLM is then restricted to generating the answer key and step-by-step feedback based only on these provided documents to eliminate hallucinations.
(cloudcuckoolander722)
1.3.3 - Structured Output:
The final output must be parsed into the APQuestion Pydantic model defined in Requirement 1.1, ensuring the source field correctly attributes the problem to its original PDF or exam year.
(cloudcuckoolander722)

1.4.1 - Textbook Semantic Search:
The system shall implement a textbook_agent (or sub-agent) tasked with performing high-density semantic searches. This agent must interface with the vertex_search_tool to query an indexed vector database containing the primary AP Chemistry textbook (e.g., Zumdahl or Brown/LeMay). Prompts must direct the subagent to teach with visual analogies that even children can grasp, and implement scientifically proven ways to explain hard concepts.
1.4.2 - Contextual Grounding (RAG):
To mitigate hallucinations, the agent shall retrieve the top k most relevant text chunks (passages, diagrams, or chemical constants) and inject them into the LLM context window. The generator must be explicitly instructed to prioritize these retrieved snippets over its internal weights for chemical properties, reaction mechanisms, and stoichiometry calculations. 
1.4.3 - Validation Logic:
The system will compare the generated MCQ/FRQ answer key against the retrieved textbook "ground truth." If a conflict is detected (e.g., an incorrect equilibrium constant), the system must re-run the textbook_agent query with a narrowed search parameter to resolve the discrepancy before returning the final APQuestion object.
(epicvstuff) - extra note, make a seperate .py file called lecturer.py

