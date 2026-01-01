import os
import json
import requests
import difflib
import re
import time
from dotenv import load_dotenv

load_dotenv()
LLM_API_KEY = os.getenv("LLM_API_KEY", "dummy")

# KNOWLEDGE BASE & PATTERNS
KNOWLEDGE_BASE = {}
ERROR_PATTERNS = []

def load_knowledge(filename):
    """
    Loads JSON data.
    - If it's error_dictionary.json (Priority Lists), it populates ERROR_PATTERNS.
    - If it's lab_manual_index.json (Citations), it updates KNOWLEDGE_BASE.
    """
    path = os.path.join("data", filename)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                
                # Check if this is the new Priority Dictionary
                # It has keys like "priority_1_syntax_and_compile"
                is_priority_dict = any(k.startswith("priority_") for k in data.keys())
                
                if is_priority_dict:
                    for category_list in data.values():
                        for err in category_list:
                            # 1. Add to Regex Detection List
                            ERROR_PATTERNS.append(err)
                            
                            # 2. Add to Knowledge Base (Key = Error Type)
                            err_type = err['type']
                            if err_type not in KNOWLEDGE_BASE:
                                KNOWLEDGE_BASE[err_type] = {}
                            KNOWLEDGE_BASE[err_type].update(err)
                else:
                    # Standard Key-Value Loading (like lab_manual_index.json)
                    for key, val in data.items():
                        if key not in KNOWLEDGE_BASE:
                            KNOWLEDGE_BASE[key] = {}
                        KNOWLEDGE_BASE[key].update(val)

            print(f"Loaded knowledge from {filename}")
        except Exception as e:
            print(f"Error loading {filename}: {e}")

# Load files
load_knowledge("error_dictionary.json")
load_knowledge("lab_manual_index.json")

# --- NEW FUNCTION: PRIORITY ANALYZER ---
def analyze_error_logs(logs):
    """
    Scans logs against ALL error patterns and returns the highest priority one.
    Priority 1 (Syntax) > Priority 2 (Runtime) > Priority 3 (Logic).
    """
    if not logs:
        return "SUCCESS", "No errors found."
        
    log_text = "\n".join(logs)
    detected_errors = []

    for err in ERROR_PATTERNS:
        # Check if the regex pattern exists in the logs
        if re.search(err['pattern'], log_text, re.IGNORECASE):
            detected_errors.append(err)

    if not detected_errors:
        return "SUCCESS", "No errors found."

    # Sort by priority (1 is most critical, 3 is least)
    # This ensures a 'scanf' warning (P1) overrides a 'Logic Error' (P3)
    best_match = min(detected_errors, key=lambda x: x['priority'])
    
    return best_match['type'], best_match['hint']

# HELPER: MINIMAL SOURCE PATCH GENERATOR
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

# LLM CALLER
def call_llm(prompt, expect_json=False):
    if not LLM_API_KEY or LLM_API_KEY == "dummy": 
        return "Set API Key in .env for AI.", None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={LLM_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = requests.post(url, json=payload, headers=headers)

            if res.status_code == 429:
                time.sleep(2)
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
            print(f"!!EXCEPTION!!: {e}") 
            return "AI Connection Error.", None

    return "AI Quota Exceeded.", None

# GENERATE HINT
def generate_hint(code, language, error_type, attempt, evidence):
    # Retrieve merged knowledge
    knowledge = KNOWLEDGE_BASE.get(error_type, {})

    # Data for the Frontend
    citation = knowledge.get("citation", "General Concept")

    # Data for the AI
    concept = knowledge.get("concept", "Unknown Error")
    template = knowledge.get("hint_template", "Explain the error clearly.")

    evidence_str = f"Error Context: {evidence}"
    expect_json = False

    if attempt <= 1:
        strategy = (
            "Attempt #1. BE VAGUE. Hint at the concept only. "
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
        strategy = (
            "Attempt #3. BE DIRECT. The student is stuck. "
            "1. Briefly state the fix. "
            "2. Provide the 'fixed_code' with that change applied."
        )
        output_instruction = (
            "Return a JSON object with keys:\n"
            "- 'hint': A concise explanation.\n"
            "- 'fixed_code': The student's code with the minimal fix applied."
        )
        expect_json = True

    # PROMPT
    prompt = f"""
    You are LabTA.

    [CONTEXT]
    Language: {language}
    Code:
    {code}

    [ERROR DATA]
    {evidence_str}

    [KNOWLEDGE BASE]
    Concept: {concept}
    Recommended Hint Style: "{template}"

    [INSTRUCTION]
    {strategy}

    [OUTPUT FORMAT]
    {output_instruction}
    """

    hint_text, fixed_code_str = call_llm(prompt, expect_json=expect_json)

    patch_diff = None
    if fixed_code_str:
        patch_diff = create_source_diff(code, fixed_code_str)

    return {
        "hint": hint_text,
        "citation": citation,
        "patch": patch_diff
    }