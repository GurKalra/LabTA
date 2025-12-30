import os
import json
import requests
import difflib
import re
import time  # NEW: For sleep/retry logic
from dotenv import load_dotenv

load_dotenv()
LLM_API_KEY = os.getenv("LLM_API_KEY", "dummy")
KNOWLEDGE_BASE = {}

# Load Citations
try:
    with open(os.path.join("data", "lab_manual_index.json"), "r") as f:
        KNOWLEDGE_BASE = json.load(f)
except: 
    pass

# ==========================================
# 1. HELPER: MINIMAL SOURCE PATCH GENERATOR
# ==========================================
def create_source_diff(user_code, fixed_code):
    user_lines = user_code.strip().splitlines()
    fixed_lines = fixed_code.strip().splitlines()
    
    diff = difflib.unified_diff(
        user_lines, 
        fixed_lines, 
        n=1, 
        lineterm=''
    )
    
    diff_list = list(diff)
    if len(diff_list) > 2:
        return "\n".join(diff_list[2:])
    return None

# ==========================================
# 2. THE BRAIN (With 429 Retry Logic)
# ==========================================
def call_llm(prompt, expect_json=False):
    if not LLM_API_KEY or LLM_API_KEY == "dummy": 
        return "Set API Key in .env for AI.", None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={LLM_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    # --- NEW: RETRY LOGIC FOR 429 ERRORS ---
    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = requests.post(url, json=payload, headers=headers)
            
            # If Rate Limited, wait and retry
            if res.status_code == 429:
                wait_time = (attempt + 1) * 2 # Wait 2s, then 4s, then 6s
                print(f"⚠️ AI Rate Limited (429). Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue

            if res.status_code != 200:
                return f"AI Error: {res.status_code}", None

            raw_text = res.json()['candidates'][0]['content']['parts'][0]['text']
            
            if expect_json:
                match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                if match:
                    clean_text = match.group(0)
                    try:
                        data = json.loads(clean_text)
                        return data.get("hint", "Check your logic."), data.get("fixed_code")
                    except json.JSONDecodeError:
                        return raw_text, None
            
            return raw_text, None

        except Exception as e:
            print(f"❌ EXCEPTION: {e}") 
            return "AI Connection Error.", None
            
    return "AI Quota Exceeded. Please try again in a minute.", None

# ==========================================
# 3. PUBLIC FUNCTION (Called by App.py)
# ==========================================
def generate_hint(code, language, error_type, attempt, evidence):
    knowledge = KNOWLEDGE_BASE.get(error_type, {})
    citation = knowledge.get("citation", "General Concept")
    
    evidence_str = f"Error Context: {evidence}"
    expect_json = False
    
    if attempt <= 1:
        strategy = (
            "Attempt #1. BE VAGUE. Hint at the concept only (e.g., 'Check your loop limits'). "
            "Do NOT reveal the solution or line numbers."
        )
        output_instruction = "Return the hint as plain text (Max 1 sentence)."
        
    elif attempt == 2:
        strategy = (
            "Attempt #2. BE SPECIFIC. Point out the exact line or variable causing the issue. "
            "Explain WHY it is wrong, but do not write the fix yet."
        )
        output_instruction = "Return the hint as plain text (Max 2 sentences)."
        
    else:
        # --- STRIKE 3: CONCISE FIX ---
        strategy = (
            "Attempt #3. BE DIRECT. The student is stuck. "
            "1. Briefly state the fix (e.g. 'Initialize sum to 0'). "
            "2. Provide the 'fixed_code' with that change applied."
        )
        output_instruction = (
            "Return a JSON object with keys:\n"
            "- 'hint': A concise explanation (Max 1-2 sentences. NO headers/lists).\n"
            "- 'fixed_code': The student's code with the minimal fix applied."
        )
        expect_json = True

    # --- CRITICAL FIX: "NO RAMBLING" INSTRUCTION ADDED ---
    prompt = f"""
    You are LabTA.
    
    [CONTEXT]
    Language: {language}
    Code:
    {code}
    
    [ERROR DATA]
    {evidence_str}
    
    [INSTRUCTION]
    {strategy}
    
    [CONSTRAINT]
    Do not "think out loud". Do not output "Here is a breakdown" or "Reasoning".
    Just provide the final output requested.
    
    [OUTPUT FORMAT]
    {output_instruction}
    """

    # ... (rest of the function remains the same) ...
    hint_text, fixed_code_str = call_llm(prompt, expect_json=expect_json)
    
    patch_diff = None
    if fixed_code_str:
        patch_diff = create_source_diff(code, fixed_code_str)

    return {
        "hint": hint_text,
        "citation": citation,
        "patch": patch_diff
    }