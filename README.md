# Google-ADK-Quizzing-Thing-

Problem Statement: Create an application implementing Google-ADK modules and agents to generate MCQ and FRQ practice problems for AP Chem. 

Requirements (Backend):

1.1 - Based on the users' search query, the program will generate the specific quota of MCQs and FRQs. Agents are assigned Python functions and Pydantic fields to store, award points, and provide feedback for the questions researched or generated.

1.2 - The system shall monitor the total token count for every outgoing request. If a request exceeds 8,192 tokens, the system shall truncate the oldest questions in the chat history until the token count is less than 7000 tokens. (will edit later)

