# ADK Quizzing Agent

AP Chemistry quizzing agent built with Google ADK (Agent Development Kit).

## Setup

- Create `quizzing_agent/.env` with `GOOGLE_API_KEY` (and optionally `GOOGLE_CLOUD_PROJECT` for Vertex).
- Install dependencies (see repo root or `requirements.txt`). Ensure `google-adk` and `google-genai` are installed for your environment.
- For the FastAPI chat UI: `pip install ag-ui-adk` (provides `ag_ui_adk`). Without it, `main.py` will fail on import; the **quiz logic** can still be tested via `test_agent.py`.

## Run the app

From `my-adk-agent/`:

```bash
python3 main.py
# or: uvicorn main:app --host 0.0.0.0 --port 8000
```

Requires `ag-ui-adk` to be installed for the `/` chat endpoint.

## Test (no UI required)

**Unit tests** (from `my-adk-agent/`):

```bash
python3 test_agent.py
```

Runs unit tests for `start_quiz`, `submit_answer`, `get_quiz_status`, and `reset_quiz` using a mock context.

**One full quiz test run** (start → answer all → status → reset):

```bash
python3 run_quiz_test.py
```

Uses a fixed 3-question quiz in memory; no LLM or network. Good for a quick sanity check of the full flow.
