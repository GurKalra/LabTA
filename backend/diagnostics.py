import re

PATTERNS = {
    # GCC/G++ Output: "temp.c:10:5: error: expected ';'"
    # Capture Groups: 1=File, 2=Line, 3=Col, 4=Type, 5=Message
    "c": r"(.*?):(\d+):(\d+): (error|warning|fatal error): (.+)",
    "cpp": r"(.*?):(\d+):(\d+): (error|warning|fatal error): (.+)",
    # Java Compiler Output (javac)
    "java": r"(.*?):(\d+): error: (.+)",
    # Python Special Case
    "python": "SPECIAL_HANDLING"
}

def clean_file_path(path: str) -> str:
    if "temp.c" in path: return "main.c"
    if "temp.cpp" in path: return "main.cpp"
    if "temp.py" in path: return "main.py"
    if "Main.java" in path: return "Main.java"
    return "code"

def parse_python_error(stderr_output: str):
    lines = stderr_output.split('\n')
    error_msg = "Runtime Error"
    line_num = "?"
    # 1. Get the Error Message
    for line in reversed(lines):
        if line.strip() and "Error:" in line:
            error_msg = line.strip()
            break
    # 2. Get the Line Number
    line_pattern = re.compile(r'File "(.*?)", line (\d+)')
    for line in lines:
        match = line_pattern.search(line)
        if match:
            line_num = match.group(2)
    return {
        "line": line_num,
        "col": "0",
        "msg": error_msg,
        "raw": stderr_output
    }

def parse_java_traceback(stderr_output: str):
    """Parses Java Runtime Stack Traces for line numbers."""
    lines = stderr_output.split('\n')
    error_msg = lines[0] if lines else "Runtime Error"
    line_num = "?"

    trace_pattern = re.compile(r'at .*?\((.*?):(\d+)\)')

    for line in lines:
        match = trace_pattern.search(line)
        if match:
            if "Main.java" in match.group(1):
                line_num = match.group(2)
                break
    return {
        "line": line_num,
        "col": "0",
        "msg": error_msg, 
        "raw": stderr_output
    }

def get_first_error(stderr_output: str, language: str):
    if not stderr_output:
        return {"line": "?", "msg": "Unknown Error", "raw": ""}

    # PYTHON SPECIAL CASE
    if language == "python":
        return parse_python_error(stderr_output)

    # STANDARD COMPILERS (C, C++, JAVA COMPILE)
    pattern = PATTERNS.get(language)
    if pattern:
        regex = re.compile(pattern)
        for line in stderr_output.split('\n'):
            match = regex.match(line.strip())
            if match:
                # FIRST ERROR LOGIC: Return immediately on first match
                if language == "java":
                    return {
                        "line": match.group(2),
                        "col": "0",
                        "msg": match.group(3).strip(),
                        "raw": line.strip()
                    }
                else: # C/C++
                    return {
                        "line": match.group(2),
                        "col": match.group(3),
                        "msg": match.group(5).strip(),
                        "raw": line.strip()
                    }

    # JAVA RUNTIME FALLBACK
    if language == "java":
        trace_result = parse_java_traceback(stderr_output)
        if trace_result["line"] != "?":
            return trace_result

    # FALLBACK
    return {
        "line": "?",
        "msg": stderr_output.strip().split('\n')[0][:150],
        "raw": stderr_output
    }