import json
import os
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

# --- INTERNAL MODULE IMPORTS ---
from backend.sandbox import run_investigation
# IMPORT THE NEW ANALYZER FUNCTION
from backend.agent import generate_hint, analyze_error_logs
from backend.diagnostics import get_first_error

# PERSISTENCE CONFIGURATION
SESSIONS_FILE = os.path.join("data", "sessions.json")
PROBLEMS_FILE = os.path.join("data", "problems.json")

def save_sessions_to_disk(sessions_dict):
    """Helper to write the current session state to JSON."""
    try:
        with open(SESSIONS_FILE, "w") as f:
            json.dump(sessions_dict, f, indent=4)
    except Exception as e:
        print(f"!!!!!!Error saving sessions: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global SESSIONS, PROBLEMS_DATA

    if os.path.exists(PROBLEMS_FILE):
        with open(PROBLEMS_FILE, "r") as f:
            PROBLEMS_DATA.update(json.load(f))
        print(f"Loaded {len(PROBLEMS_DATA)} problems.")

    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r") as f:
                SESSIONS.update(json.load(f))
            print(f"Loaded {len(SESSIONS)} existing sessions.")
        except json.JSONDecodeError:
            print("!!sessions.json was empty or corrupt, starting fresh.")

    yield

    print("Saving sessions before shutdown...")
    save_sessions_to_disk(SESSIONS)

# 2. APPLICATION SETUP
app = FastAPI(
    title="LabTA Backend",
    description="AI-Powered Debugging Assistant",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSIONS: Dict[str, Dict] = {}
PROBLEMS_DATA: Dict[str, Any] = {}

# 3. API DATA MODELS
class SubmitRequest(BaseModel):
    user_id: str
    problem_id: str
    language: str
    code: str

# Saving Requests
class SaveRequest(BaseModel):
    user_id: str
    problem_id: str
    code: str

# 4. API ENDPOINTS

@app.get("/")
def health_check():
    return {"status": "LabTA is Online"}

@app.get("/problems")
def get_problems():
    sanitized = {}
    for pid, data in PROBLEMS_DATA.items():
        sanitized[pid] = {
            "title": data.get("title"),
            "description": data.get("description"),
            "sample_cases": data.get("sample_cases"),
            "difficulty": data.get("difficulty", "Unknown"),
            "case_count": len(data.get("hidden_cases", []))
        }
    return sanitized

@app.get("/sessions")
def get_all_sessions():
    return SESSIONS

@app.get("/draft/{user_id}/{problem_id}")
def get_draft(user_id: str, problem_id: str):
    """
    Returns the MANUALLY SAVED code for a specific user and problem.
    """
    session_key = f"{user_id}_{problem_id}"
    user_state = SESSIONS.get(session_key, {})

    return {
        "draft_code": user_state.get("draft_code", None),
        "attempts": user_state.get("attempt", 0),
        "last_error": user_state.get("last_error", None)
    }

#MANUAL SAVE
@app.post("/save")
def save_draft(request: SaveRequest):
    """
    Called ONLY when the user clicks the 'Save' button.
    Does NOT run the code. Just persists it to disk.
    """
    session_key = f"{request.user_id}_{request.problem_id}"
    user_state = SESSIONS.get(session_key, {"last_error": None, "attempt": 0})

    user_state["draft_code"] = request.code

    SESSIONS[session_key] = user_state
    save_sessions_to_disk(SESSIONS)

    return {"status": "SAVED", "message": "Code saved successfully."}

@app.post("/submit")
def submit_code(request: SubmitRequest):

    user_id = request.user_id
    problem_id = request.problem_id

    if problem_id not in PROBLEMS_DATA:
        raise HTTPException(status_code=404, detail="Problem ID not found")

    # 1. Run the Sandbox
    logs, raw_status, evidence = run_investigation(
        code=request.code,
        language=request.language,
        problem_id=problem_id,
        problems_db=PROBLEMS_DATA
    )

    # 2. **CRITICAL FIX: PRIORITY ANALYSIS**
    # We now call the Agent to scan the logs for "hidden" high-priority errors (like scanf warnings)
    detected_type, detected_hint = analyze_error_logs(logs)

    # If the Analyzer finds a Priority 1 or 2 error (Syntax/Runtime), we USE IT.
    # This OVERRIDES "LOGIC_ERROR" (Priority 3) if a Priority 1 error exists.
    if detected_type != "SUCCESS" and raw_status == "LOGIC_ERROR":
        final_status = detected_type
        # We replace the confusing "diff" evidence with the clear specific hint (e.g., "Check your scanf")
        clean_evidence = detected_hint
        logs.append(f"\n[Agent Override] Logic Error masked by Critical Warning: {detected_type}")
    else:
        final_status = raw_status
        clean_evidence = evidence

    # Standard cleaning for raw sandbox errors
    if final_status in ["SYNTAX_ERROR", "RUNTIME_ERROR"] and isinstance(evidence, str):
        diag = get_first_error(evidence, request.language)
        clean_evidence = f"Line {diag['line']}: {diag['msg']}"

    # 3. Session Management
    session_key = f"{user_id}_{problem_id}"
    user_state = SESSIONS.get(session_key, {"last_error": None, "attempt": 0})
    system_messages = []

    if final_status == "SUCCESS":
        system_messages.append(f"**Great Job!** You passed all tests.")
        user_state["attempt"] = 0
    elif user_state["last_error"] == final_status:
        user_state["attempt"] += 1
        system_messages.append(f"**Issue Persists:** Attempt #{user_state['attempt']} at fixing {final_status}.")
    else:
        user_state["attempt"] = 1
        system_messages.append(f"**New Challenge:** Encountered a {final_status}.")

    user_state["last_error"] = final_status

    SESSIONS[session_key] = user_state
    save_sessions_to_disk(SESSIONS)

    # 4. Generate AI Hint & Patch
    hint = "Congratulations! You are ready for the next challenge."
    citation = ""
    patch = None

    if final_status != "SUCCESS":
        agent_res = generate_hint(
            code=request.code,
            language=request.language,
            error_type=final_status,
            attempt=user_state["attempt"],
            evidence=clean_evidence
        )

        hint = agent_res.get("hint")
        citation = agent_res.get("citation")
        patch = agent_res.get("patch")

        # Logic Errors unlock diffs after 3 attempts
        if final_status == "LOGIC_ERROR" and user_state["attempt"] >= 3:
            logs.append("\n**Diff Analysis Unlocked (Attempt 3+):**")
            logs.append(evidence.get("diff", "No output diff available.") if isinstance(evidence, dict) else "")
            system_messages.append("**Source Patch Unlocked:** A suggested code fix is now available.")

    return {
        "status": final_status,
        "agent_logs": logs,
        "system_messages": system_messages,
        "hint": hint,
        "citation": citation,
        "patch": patch
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)