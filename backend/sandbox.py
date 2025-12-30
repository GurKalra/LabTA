import subprocess
import os
import sys
import difflib
import uuid
import shutil

# ==========================================
# 1. CONFIGURATION
# ==========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DIR = os.path.join(BASE_DIR, "temp_workspace")

# Ensure the main workspace exists and is writable by Docker
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)
try:
    os.chmod(TEMP_DIR, 0o777)
except:
    pass # harmless if already set

DOCKER_IMAGE = "lab-ta-runner"
TIMEOUT_SEC = 5 

# ==========================================
# 2. HELPER: DOCKER EXECUTION ENGINE
# ==========================================

def run_in_docker(commands, input_str, work_dir):
    # Escape single quotes for shell safety
    safe_input = input_str.replace("'", "'\\''")
    cmd_chain = " && ".join(commands)
    
    # Run inside a subshell ( ) to ensure piping works for the whole chain
    full_cmd = f"echo '{safe_input}' | ( {cmd_chain} )"
    
    docker_run_cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", "256m",
        "--cpus", "0.5",
        "-v", f"{work_dir}:/app", # Mount the UNIQUE folder
        DOCKER_IMAGE,
        "bash", "-c", full_cmd
    ]

    try:
        res = subprocess.run(docker_run_cmd, capture_output=True, text=True, timeout=TIMEOUT_SEC)
        
        # Check for Segfaults (Exit Code 139)
        if res.returncode in [139, 11]:
            return 139, "", "Segmentation Fault (Memory Access Error)"
            
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "TIMEOUT"

def generate_diff(expected, actual):
    expected_lines = expected.strip().splitlines()
    actual_lines = actual.strip().splitlines()
    diff = difflib.ndiff(expected_lines, actual_lines)
    
    report = []
    has_diff = False
    for line in diff:
        if line.startswith('- '): report.append(f"❌ EXPECTED: {line[2:]}"); has_diff = True
        elif line.startswith('+ '): report.append(f"⚠️ ACTUAL:   {line[2:]}"); has_diff = True
        elif not line.startswith('? '): report.append(f"✅ MATCH:    {line[2:]}")
    return "\n".join(report) if has_diff else "Hidden character mismatch."

# ==========================================
# 3. LANGUAGE RUNNERS (With explicit 777 permissions)
# ==========================================

def run_c(code, input_str):
    job_id = uuid.uuid4().hex
    work_dir = os.path.join(TEMP_DIR, job_id)
    os.makedirs(work_dir, exist_ok=True)
    os.chmod(work_dir, 0o777) # <--- CRITICAL FIX: Allow Docker to write here
    
    try:
        # Write source file and make it writable
        with open(os.path.join(work_dir, "main.c"), "w") as f: f.write(code)
        os.chmod(os.path.join(work_dir, "main.c"), 0o777)

        cmds = ["gcc /app/main.c -o /app/main.out", "/app/main.out"]
        ret, out, err = run_in_docker(cmds, input_str, work_dir)
        
        if "error:" in err and ("gcc" in err or "main.c" in err): return "COMPILE_ERROR", err
        if ret == 124: return "TIMEOUT", "Execution timed out"
        if ret == 139: return "SEGFAULT_ERROR", "Memory Access Violation"
        return ("SUCCESS", out) if ret == 0 else ("RUNTIME_ERROR", err)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True) # Cleanup

def run_cpp(code, input_str):
    job_id = uuid.uuid4().hex
    work_dir = os.path.join(TEMP_DIR, job_id)
    os.makedirs(work_dir, exist_ok=True)
    os.chmod(work_dir, 0o777) # <--- CRITICAL FIX
    
    try:
        with open(os.path.join(work_dir, "main.cpp"), "w") as f: f.write(code)
        os.chmod(os.path.join(work_dir, "main.cpp"), 0o777)

        cmds = ["g++ /app/main.cpp -o /app/main.out", "/app/main.out"]
        ret, out, err = run_in_docker(cmds, input_str, work_dir)
        
        if "error:" in err and ("g++" in err or "main.cpp" in err): return "COMPILE_ERROR", err
        if ret == 124: return "TIMEOUT", "Execution timed out"
        if ret == 139: return "SEGFAULT_ERROR", "Memory Access Violation"
        return ("SUCCESS", out) if ret == 0 else ("RUNTIME_ERROR", err)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

def run_python(code, input_str):
    job_id = uuid.uuid4().hex
    work_dir = os.path.join(TEMP_DIR, job_id)
    os.makedirs(work_dir, exist_ok=True)
    os.chmod(work_dir, 0o777) # <--- CRITICAL FIX
    
    try:
        with open(os.path.join(work_dir, "main.py"), "w") as f: f.write(code)
        os.chmod(os.path.join(work_dir, "main.py"), 0o777)

        cmds = ["python3 /app/main.py"]
        ret, out, err = run_in_docker(cmds, input_str, work_dir)
        
        if any(kw in err for kw in ["SyntaxError", "IndentationError", "TabError"]):
            return "COMPILE_ERROR", err
        if ret == 124: return "TIMEOUT", "Execution timed out"
        return ("SUCCESS", out) if ret == 0 else ("RUNTIME_ERROR", err)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

def run_java(code, input_str):
    job_id = uuid.uuid4().hex
    work_dir = os.path.join(TEMP_DIR, job_id)
    os.makedirs(work_dir, exist_ok=True)
    os.chmod(work_dir, 0o777) # <--- CRITICAL FIX
    
    try:
        with open(os.path.join(work_dir, "Main.java"), "w") as f: f.write(code)
        os.chmod(os.path.join(work_dir, "Main.java"), 0o777)

        cmds = ["javac /app/Main.java", "java -cp /app Main"]
        ret, out, err = run_in_docker(cmds, input_str, work_dir)
        
        if "error:" in err and ("javac" in err or "Main.java" in err):
            return "COMPILE_ERROR", err
        if ret == 124: return "TIMEOUT", "Execution timed out"
        return ("SUCCESS", out) if ret == 0 else ("RUNTIME_ERROR", err)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

# ==========================================
# 5. THE DISPATCHER
# ==========================================

RUNNERS = {"c": run_c, "cpp": run_cpp, "python": run_python, "java": run_java}

def run_investigation(code, language, problem_id, problems_db):
    logs = []
    logs.append(f"🔵 Phase 1: Initializing Docker Sandbox for {language.upper()}...")

    runner = RUNNERS.get(language)
    problem = problems_db.get(problem_id)
    if not runner: return logs, "SYSTEM_ERROR", "Language unsupported"
    if not problem: return logs, "SYSTEM_ERROR", "Problem ID missing"

    hidden_cases = problem.get("hidden_cases", [])
    logs.append(f"⚙️ Phase 2: Loading {len(hidden_cases)} isolated test cases...")

    for index, case in enumerate(hidden_cases):
        case_input = case["input"]
        case_expected = case["output"].strip()
        
        logs.append(f"🧪 Phase 3: Running Test Case #{index + 1}...")
        status, output = runner(code, case_input)
        output = output.strip() if output else ""

        if status == "COMPILE_ERROR":
            return logs, "SYNTAX_ERROR", output
        if status == "RUNTIME_ERROR":
            return logs, "RUNTIME_ERROR", output
        if status == "SEGFAULT_ERROR":
            return logs, "SEGFAULT_ERROR", "Memory Access Violation"
        if status == "TIMEOUT":
            return logs, "TIME_LIMIT_EXCEEDED", "Code took too long."

        if output != case_expected:
            logs.append("❌ Failure: Logic Mismatch.")
            diff_view = generate_diff(case_expected, output)
            evidence = {"expected": case_expected, "actual": output, "diff": diff_view}
            return logs, "LOGIC_ERROR", evidence

    logs.append("🎉 Result: Passed all hidden test cases.")
    return logs, "SUCCESS", None