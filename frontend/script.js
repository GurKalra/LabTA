/**
 * LabTA - Frontend Logic Controller
 * Handles: Session Management, Code Execution, Draft Persistence, and UI Resizing
 */

const API_BASE = "http://localhost:8000";

// 1. SESSION MANAGEMENT
// Retrieves user_id from localStorage or sets a default for the session
let USER_ID = localStorage.getItem("labta_user_id");
if (!USER_ID) {
  USER_ID = "student_" + Math.floor(Math.random() * 9000 + 1000);
  localStorage.setItem("labta_user_id", USER_ID);
}

// Get problem ID from the URL (e.g., problem.html?id=basic_01_leap)
const urlParams = new URLSearchParams(window.location.search);
const PROBLEM_ID = urlParams.get("id");

// 2. EDITOR INITIALIZATION
const editorElement = document.getElementById("editor-textarea");
let editor;

if (editorElement) {
  editor = CodeMirror.fromTextArea(editorElement, {
    lineNumbers: true,
    theme: "dracula",
    mode: "python",
    indentUnit: 4,
    autoCloseBrackets: true,
    matchBrackets: true,
    lineWrapping: true,
  });
}

// 3. UI: DYNAMIC RESIZING (The "Edge")
const resizer = document.getElementById("dragMe");
const leftSide = document.getElementById("left-sidebar");

if (resizer && leftSide) {
  resizer.addEventListener("mousedown", (e) => {
    document.addEventListener("mousemove", resizeHandler);
    document.addEventListener("mouseup", () => {
      document.removeEventListener("mousemove", resizeHandler);
      resizer.classList.remove("active");
    });
    resizer.classList.add("active");
  });
}

function resizeHandler(e) {
  const newWidth = e.clientX;
  // Constraints: Don't let the sidebar get too small or too huge
  if (newWidth > 200 && newWidth < 650) {
    leftSide.style.width = newWidth + "px";
  }
}

// 4. BACKEND SYNC: LOAD PROBLEM & DRAFT
async function syncIDE() {
  if (!PROBLEM_ID) {
    alert("No Problem ID specified. Returning to selection.");
    window.location.href = "selection.html";
    return;
  }

  try {
    // Fetch specific problem data from problems.json (via backend)
    const pResponse = await fetch(`${API_BASE}/problems`);
    const allProblems = await pResponse.json();
    const problemData = allProblems[PROBLEM_ID];

    if (!problemData) throw new Error("Problem not found in database.");

    // Update UI Text
    document.getElementById("prob-title").innerText = problemData.title;
    document.getElementById("prob-desc").innerText = problemData.description;
    document.getElementById("prob-diff").innerText = problemData.difficulty;

    // Show the first sample case
    if (problemData.sample_cases && problemData.sample_cases.length > 0) {
      document.getElementById("sample-input").innerText =
        problemData.sample_cases[0].input;
      document.getElementById("sample-output").innerText =
        problemData.sample_cases[0].output;
    }

    // --- ATTEMPT TO LOAD SAVED DRAFT ---
    // Hits @app.get("/draft/{user_id}/{problem_id}")
    const dResponse = await fetch(`${API_BASE}/draft/${USER_ID}/${PROBLEM_ID}`);
    if (dResponse.ok) {
      const draftData = await dResponse.json();
      if (draftData.draft_code) {
        editor.setValue(draftData.draft_code);
      }
    }
  } catch (err) {
    console.error("Sync Error:", err);
    document.getElementById(
      "agent-console"
    ).innerHTML = `<div class="log-entry error">> Error: ${err.message}</div>`;
  }
}

// 5. ACTION: SAVE DRAFT
// Triggered by the "Save Draft" button
async function handleSave() {
  const code = editor.getValue();
  const saveBtn = document.getElementById("save-btn");

  saveBtn.innerText = "Saving...";
  saveBtn.disabled = true;

  try {
    const response = await fetch(`${API_BASE}/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: USER_ID,
        problem_id: PROBLEM_ID,
        code: code,
      }),
    });

    if (response.ok) {
      saveBtn.innerText = "✅ Saved";
      setTimeout(() => {
        saveBtn.innerText = "💾 Save Draft";
        saveBtn.disabled = false;
      }, 2000);
    }
  } catch (err) {
    alert("Failed to save progress. Check backend connection.");
    saveBtn.disabled = false;
  }
}

// 6. ACTION: RUN & SUBMIT
// Triggered by "Run & Submit" button. Handles Docker execution and AI Hint rendering.
async function handleRun() {
  const consoleDiv = document.getElementById("agent-console");
  const hintDiv = document.getElementById("ai-hints");
  const lang = document.getElementById("language-select").value;

  // UI Feedback
  consoleDiv.innerHTML = `<div class="log-entry">> Initializing Docker Runner [${lang.toUpperCase()}]...</div>`;
  hintDiv.innerHTML = `<div class="loading-spinner">AI Agent is analyzing your code logic...</div>`;

  try {
    const response = await fetch(`${API_BASE}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: USER_ID,
        problem_id: PROBLEM_ID,
        language: lang,
        code: editor.getValue(),
      }),
    });

    const data = await response.json();

    // 1. Render Sandbox Logs
    consoleDiv.innerHTML = data.agent_logs
      .map((log) => {
        const isError = log.includes("❌") || log.includes("Failure");
        return `<div class="log-entry ${
          isError ? "error" : ""
        }">> ${log}</div>`;
      })
      .join("");

    // 2. Render AI Hint Card
    // The data comes from the AI using error_dictionary.json and lab_manual_index.json
    hintDiv.innerHTML = `
            <div class="hint-card">
                <div class="hint-status ${data.status.toLowerCase()}">${
      data.status
    }</div>
                <p class="hint-text">${data.hint}</p>
                ${
                  data.citation
                    ? `<div class="hint-citation">📖 Reference: ${data.citation}</div>`
                    : ""
                }
            </div>
        `;

    // 3. Render Patch (Unlocked after Attempt 3 or for specific errors)
    if (data.patch) {
      hintDiv.innerHTML += `
                <div class="patch-container">
                    <h4>Suggested Modification:</h4>
                    <pre class="patch-code">${data.patch}</pre>
                    <button class="btn btn-save" style="width:100%; margin-top:10px" onclick="applyPatch(\`${data.patch.replace(
                      /`/g,
                      "\\`"
                    )}\`)">
                        Apply Fix
                    </button>
                </div>
            `;
    }

    // Scroll terminal to bottom
    consoleDiv.scrollTop = consoleDiv.scrollHeight;
  } catch (err) {
    consoleDiv.innerHTML += `<div class="log-entry error">> Backend Communication Failure. Is FastAPI running?</div>`;
  }
}

// Helper to apply the AI's suggested patch to the editor
window.applyPatch = function (patchCode) {
  // Note: In a production environment, you'd use a diff-patch library.
  // For this lab, we inform the user to review the patch-code block.
  alert(
    "Please review the suggested fix in the hint panel and apply the logic to your code."
  );
};

// INITIALIZE
document.addEventListener("DOMContentLoaded", () => {
  if (PROBLEM_ID) syncIDE();

  const saveBtn = document.getElementById("save-btn");
  const runBtn = document.getElementById("run-btn");

  if (saveBtn) saveBtn.onclick = handleSave;
  if (runBtn) runBtn.onclick = handleRun;
});
