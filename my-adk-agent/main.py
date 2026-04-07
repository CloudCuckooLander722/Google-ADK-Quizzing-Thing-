from quizzing_agent.agent import root_agent

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
import google.api_core.exceptions as exceptions
from google.api_core import retry

app = FastAPI(title="ADK Quizzing Agent")

adk_agent_wrapper = ADKAgent(adk_agent=root_agent, app_name="quiz_master", user_id="default", session_timeout_seconds=3600, use_in_memory_services=True)

add_adk_fastapi_endpoint(app, adk_agent_wrapper, path="/")

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exceptions: Exception):
    print(f"❌ Internal Error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "The agent hit a snag. Please check your API key or connection."
        },
    )


@app.exception_handler(exceptions.ResourceExhausted)
async def rate_limit_handler(request: Request, exc: exceptions.ResourceExhausted):
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "message": "The Quiz Master is taking a breather. Please wait a few seconds or refresh the chat!"
        },
    )




if __name__ == "__main__":
    import os
    import uvicorn

    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  Warning: GOOGLE_API_KEY environment variable not set!")
        print("   Set it with: export GOOGLE_API_KEY='your-key-here'")
        print("   Get a key from: https://makersuite.google.com/app/apikey")
        print()
    
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(app, host="0.0.0.0", port=port)
    