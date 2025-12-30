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

if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)
try:
    os.chmod(TEMP_DIR, 0o777)
except:
    pass

DOCKER_IMAGE = "lab-ta-runner"
TIMEOUT_SEC = 5 

# ==========================================
# 2. HELPER: DOCKER EXECUTION ENGINE
# ==========================================

def run_in_docker(commands, input_str, work_dir):
    safe_input = input_str.replace("'", "'\\''")
    cmd_chain = " && ".join(commands)
    full_cmd = f"echo '{safe_input}' | ( {cmd_chain} )"
    
    docker_run_cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", "256m",     # Limits memory to 256MB
        "--cpus", "0.5",
        "-v", f"{work_dir}:/app",
        DOCKER_IMAGE,
        "bash", "-c", full_cmd
    ]

    try:
        res = subprocess.run(docker_run_cmd, capture_output=True, text=True, timeout=TIMEOUT_SEC)
        
        # --- NEW: ADVANCED EXIT CODE ANALYSIS ---
        if res.returncode == 137: # Docker OOM Kill (Out of Memory)
            return 137, "", "Memory Limit Exceeded"
        if res.returncode in [139, 11]: # Segfault
            return 139, "", "Segmentation Fault"
            
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
# 3. LANGUAGE RUNNERS (Enhanced Detection)
# ==========================================

def run_c(code, input_str):
    job_id = uuid.uuid4().hex
    work_dir = os.path.join(TEMP_DIR, job_id)
    os.makedirs(work_dir, exist_ok=True)
    os.chmod(work_dir, 0o777)
    
    try:
        with open(os.path.join(work_dir, "main.c"), "w") as f: f.write(code)
        os.chmod(os.path.join(work_dir, "main.c"), 0o777)

        cmds = ["gcc /app/main.c -o /app/main.out", "/app/main.out"]
        ret, out, err = run_in_docker(cmds, input_str, work_dir)
        
        # C Compilation Errors
        if "error:" in err and ("gcc" in err or "main.c" in err):
            return "COMPILATION_ERROR","", err
            
        return ret, out, err
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

def run_cpp(code, input_str):
    job_id = uuid.uuid4().hex
    work_dir = os.path.join(TEMP_DIR, job_id)
    os.makedirs(work_dir, exist_ok=True)
    os.chmod(work_dir, 0o777)
    
    try:
        with open(os.path.join(work_dir, "main.cpp"), "w") as f: f.write(code)
        os.chmod(os.path.join(work_dir, "main.cpp"), 0o777)

        cmds = ["g++ /app/main.cpp -o /app/main.out", "/app/main.out"]
        ret, out, err = run_in_docker(cmds, input_str, work_dir)
        
        if "error:" in err and ("g++" in err or "main.cpp" in err):
            return "COMPILATION_ERROR", "", err
            
        return ret, out, err
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

def run_python(code, input_str):
    job_id = uuid.uuid4().hex
    work_dir = os.path.join(TEMP_DIR, job_id)
    os.makedirs(work_dir, exist_ok=True)
    os.chmod(work_dir, 0o777)
    
    try:
        with open(os.path.join(work_dir, "main.py"), "w") as f: f.write(code)
        os.chmod(os.path.join(work_dir, "main.py"), 0o777)

        cmds = ["python3 /app/main.py"]
        ret, out, err = run_in_docker(cmds, input_str, work_dir)
        
        # Python Specific Error Analysis
        if "SyntaxError" in err or "IndentationError" in err:
            return "SYNTAX_ERROR", "", err
        if "TypeError" in err:
            return "TYPE_ERROR", "", err
            
        return ret, out, err
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

def run_java(code, input_str):
    job_id = uuid.uuid4().hex
    work_dir = os.path.join(TEMP_DIR, job_id)
    os.makedirs(work_dir, exist_ok=True)
    os.chmod(work_dir, 0o777)
    
    try:
        with open(os.path.join(work_dir, "Main.java"), "w") as f: f.write(code)
        os.chmod(os.path.join(work_dir, "Main.java"), 0o777)

        cmds = ["javac /app/Main.java", "java -cp /app Main"]
        ret, out, err = run_in_docker(cmds, input_str, work_dir)
        
        if "error:" in err and ("javac" in err or "Main.java" in err):
            return "COMPILATION_ERROR", "", err
        
        if "ClassCastException" in err:
            return "TYPE_ERROR", "", err
            
        return ret, out, err
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

# ==========================================
# 5. THE DISPATCHER (Maps to 10 Error Types)
# ==========================================

RUNNERS = {"c": run_c, "cpp": run_cpp, "python": run_python, "java": run_java}

def run_investigation(code, language, problem_id, problems_db):
    logs = []
    logs.append(f"🔵 Phase 1: Initializing Docker Sandbox for {language.upper()}...")

    runner = RUNNERS.get(language)
    problem = problems_db.get(problem_id)
    if not runner: return logs, "SYSTEM_ERROR", "Language unsupported"
    
    hidden_cases = problem.get("hidden_cases", [])
    logs.append(f"⚙️ Phase 2: Loading {len(hidden_cases)} isolated test cases...")

    for index, case in enumerate(hidden_cases):
        case_input = case["input"]
        case_expected = case["output"].strip()
        
        logs.append(f"🧪 Phase 3: Running Test Case #{index + 1}...")
        
        # Call the runner (Now returns ret, out, err OR explicit status)
        result = runner(code, case_input)
        
        # Check if runner returned a tuple (ret, out, err) or specific error code
        if isinstance(result[0], int):
            ret, output, err = result
            status = "UNKNOWN_ERROR"
        else:
            # Runner returned explicit error (e.g., "TYPE_ERROR", "", err)
            status_code, output, err = result
            if status_code in ["SYNTAX_ERROR", "COMPILATION_ERROR", "TYPE_ERROR"]:
                return logs, status_code, err
            ret = -1 # Placeholder

        # --- ADVANCED MAPPING LOGIC ---
        output = output.strip() if output else ""

        # 1. TIMEOUT
        if ret == 124:
            return logs, "TIME_LIMIT_EXCEEDED", "Code took too long to execute."

        # 2. MEMORY LIMIT (Docker Exit 137)
        if ret == 137:
            return logs, "MEMORY_LIMIT_EXCEEDED", "Process killed (OOM)."

        # 3. SEGFAULT (Docker Exit 139)
        if ret == 139:
            return logs, "SEGFAULT_ERROR", "Memory Access Violation."

        # 4. RUNTIME ERROR (Generic Non-Zero)
        if ret != 0:
            return logs, "RUNTIME_ERROR", err

        # 5. INPUT/OUTPUT ERROR (Empty Output)
        if ret == 0 and not output and case_expected:
             return logs, "INPUT_OUTPUT_ERROR", "Program finished but produced no output."

        # 6. LOGIC ERROR (Output Mismatch)
        if output != case_expected:
            logs.append("❌ Failure: Logic Mismatch.")
            diff_view = generate_diff(case_expected, output)
            evidence = {"expected": case_expected, "actual": output, "diff": diff_view}
            return logs, "LOGIC_ERROR", evidence

    logs.append("🎉 Result: Passed all hidden test cases.")
    return logs, "SUCCESS", None