import re


PATTERNS = {
    # GCC/G++ Output: "temp.c:10:5: error: expected ';'"
    # Capture Groups: 1=File, 2=Line, 3=Col, 4=Type, 5=Message
    "c": r"(.*?):(\d+):(\d+): (error|warning|fatal error): (.+)",
    "cpp": r"(.*?):(\d+):(\d+): (error|warning|fatal error): (.+)",
    
    # Java Output: "Main.java:12: error: ';' expected"
    # Capture Groups: 1=File, 2=Line, 3=Message
    "java": r"(.*?):(\d+): error: (.+)",
    
    # Python Traceback is unique (Multi-line). 
    # We use a special function logic for Python instead of a single regex.
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
    line_num = "Unknown"
    
    for line in reversed(lines):
        if line.strip() and "Error:" in line:
            error_msg = line.strip()
            break
            
    # 2. Find the Line Number
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

def get_first_error(stderr_output: str, language: str):
    if not stderr_output:
        return {"line": "?", "msg": "Unknown Error", "raw": ""}

    # PYTHON SPECIAL CASE
    if language == "python":
        return parse_python_error(stderr_output)

    # STANDARD COMPILERS (C, C++, JAVA)
    pattern = PATTERNS.get(language)
    if not pattern:
        # Fallback if language unknown
        return {"line": "?", "msg": stderr_output[:100], "raw": stderr_output}

    # Iterate line by line to find the FIRST error (ignore warnings if possible)
    lines = stderr_output.split('\n')
    regex = re.compile(pattern)

    for line in lines:
        match = regex.match(line.strip())
        if match:
            # Extraction Logic based on language groups
            if language == "java":
                return {
                    "line": match.group(2),
                    "col": "0",
                    "msg": match.group(3).strip(),
                    "raw": line.strip()
                }
            else:
                return {
                    "line": match.group(2),
                    "col": match.group(3),
                    "msg": match.group(5).strip(),
                    "raw": line.strip()
                }

    # If Regex failed to match anything (weird compiler output), return raw
    return {
        "line": "?", 
        "msg": stderr_output.strip().split('\n')[0][:100], 
        "raw": stderr_output
    }