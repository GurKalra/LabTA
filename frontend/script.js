/* CONFIGURATION */
const API_BASE = "http://localhost:8000";

// Generate or retrieve a persistent User ID
let USER_ID = localStorage.getItem("labta_user_id");
if (!USER_ID) {
  USER_ID = "student_" + Math.floor(Math.random() * 9000 + 1000);
  localStorage.setItem("labta_user_id", USER_ID);
}

// Get Problem ID from URL
const urlParams = new URLSearchParams(window.location.search);
const PROBLEM_ID = urlParams.get("id");

// CodeMirror Editor Instance
let editor;

document.addEventListener("DOMContentLoaded", async () => {
  // A. Initialize CodeMirror
  const textarea = document.getElementById("editor-textarea");
  if (textarea) {
    editor = CodeMirror.fromTextArea(textarea, {
      lineNumbers: true,
      theme: "dracula",
      mode: "python", // Default
      indentUnit: 4,
      autoCloseBrackets: true,
      matchBrackets: true,
      lineWrapping: true,
      viewportMargin: Infinity,
    });
  }

  setupResizer();

  const saveBtn = document.getElementById("save-btn");
  const runBtn = document.getElementById("run-btn");
  const langSelect = document.getElementById("language-select");

  if (saveBtn) saveBtn.addEventListener("click", handleSave);
  if (runBtn) runBtn.addEventListener("click", handleRun);

  // Language Switcher Logic
  if (langSelect) {
    langSelect.addEventListener("change", (e) => {
      const lang = e.target.value;
      const modeMap = {
        python: "python",
        c: "text/x-csrc",
        cpp: "text/x-c++src",
        java: "text/x-java",
      };
      editor.setOption("mode", modeMap[lang] || "python");
    });
  }

  // C. Load Data
  if (PROBLEM_ID) {
    await loadProblemData();
    await loadDraft();
  } else {
    alert("No Problem ID found. Redirecting to selection.");
    window.location.href = "selection.html";
  }
});

function setupResizer() {
  const resizer = document.getElementById("dragMe");
  const leftSide = document.getElementById("left-sidebar");

  if (!resizer || !leftSide) return;

  let x = 0;
  let leftWidth = 0;

  const mouseDownHandler = function (e) {
    x = e.clientX;
    leftWidth = leftSide.getBoundingClientRect().width;

    document.addEventListener("mousemove", mouseMoveHandler);
    document.addEventListener("mouseup", mouseUpHandler);

    resizer.classList.add("active");
    // Prevent text selection while dragging
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
  };

  const mouseMoveHandler = function (e) {
    const dx = e.clientX - x;
    const newWidth = leftWidth + dx;
    if (newWidth > 200 && newWidth < 600) {
      leftSide.style.width = `${newWidth}px`;
    }
  };

  const mouseUpHandler = function () {
    document.removeEventListener("mousemove", mouseMoveHandler);
    document.removeEventListener("mouseup", mouseUpHandler);

    resizer.classList.remove("active");
    document.body.style.removeProperty("user-select");
    document.body.style.removeProperty("cursor");
  };

  resizer.addEventListener("mousedown", mouseDownHandler);
}

/* HELPER: TOAST NOTIFICATIONS */
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return; // Guard clause if HTML is missing

  // Create Box
  const box = document.createElement("div");
  box.className = `toast-box ${type}`;

  // Icon Logic
  let icon = "ℹ️";
  if (type === "success") icon = "✅";
  if (type === "error") icon = "❌";

  box.innerHTML = `
      <span style="font-size:1.2em">${icon}</span>
      <span>${message}</span>
    `;

  // Add to DOM
  container.appendChild(box);

  // Remove after 3 seconds
  setTimeout(() => {
    box.classList.add("fade-out");
    box.addEventListener("animationend", () => {
      if (box.parentNode) box.remove();
    });
  }, 3000);
}

/* BACKEND SYNC */

// A. Load Problem Details
async function loadProblemData() {
  try {
    const res = await fetch(`${API_BASE}/problems`);
    if (!res.ok) throw new Error("Failed to fetch problems");

    const problems = await res.json();
    const p = problems[PROBLEM_ID];

    if (!p) {
      document.getElementById("prob-title").innerText = "Problem Not Found";
      return;
    }

    document.getElementById("prob-title").innerText = p.title;
    document.getElementById("prob-desc").innerText = p.description;

    const diffEl = document.getElementById("prob-diff");
    diffEl.innerText = p.difficulty;

    if (p.difficulty === "Hard") diffEl.style.color = "#f85149";
    else if (p.difficulty === "Medium") diffEl.style.color = "#d29922";

    // Sample Cases
    if (p.sample_cases && p.sample_cases.length > 0) {
      document.getElementById("sample-input").innerText =
        p.sample_cases[0].input;
      document.getElementById("sample-output").innerText =
        p.sample_cases[0].output;
    }
  } catch (err) {
    console.error("Problem Load Error:", err);
    showToast("Error loading problem data. Is backend running?", "error");
  }
}

// Load Saved Draft
async function loadDraft() {
  try {
    const res = await fetch(`${API_BASE}/draft/${USER_ID}/${PROBLEM_ID}`);
    if (res.ok) {
      const data = await res.json();
      if (data.draft_code) {
        editor.setValue(data.draft_code);
        console.log("Draft loaded.");
      }
    }
  } catch (err) {
    console.log("No existing draft or backend offline.");
  }
}

// Save Draft
async function handleSave() {
  const btn = document.getElementById("save-btn");

  btn.innerText = "Saving...";
  btn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: USER_ID,
        problem_id: PROBLEM_ID,
        code: editor.getValue(),
      }),
    });

    if (res.ok) {
      showToast("Draft saved successfully!", "success");
    } else {
      throw new Error("Save failed");
    }
  } catch (err) {
    showToast("Failed to save. Check backend connection.", "error");
  } finally {
    // Restore button immediately
    btn.innerText = "Save Draft";
    btn.disabled = false;
  }
}

/* EXECUTION & AI LOGIC */

async function handleRun() {
  const consoleDiv = document.getElementById("agent-console");
  const hintDiv = document.getElementById("ai-hints");
  const runBtn = document.getElementById("run-btn");
  const lang = document.getElementById("language-select").value;

  // Set UI to Loading State
  runBtn.disabled = true;
  runBtn.style.opacity = "0.7";

  consoleDiv.innerHTML = `<div class="log-entry" style="color:#d29922">> Initializing Docker Container [${lang}]...</div>`;
  hintDiv.innerHTML = `
    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100px; color:#8b949e;">
        <div class="loader" style="margin-bottom:10px">⏳</div>
        Analyzing logic & output...
    </div>`;

  try {
    // Submit Code
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

    // Render Terminal Logs
    consoleDiv.innerHTML = data.agent_logs
      .map((log) => {
        const isError = /error|fail|exception/i.test(log);
        const colorClass = isError
          ? 'style="color:#f85149"'
          : 'style="color:#4ade80"';
        return `<div class="log-entry" ${colorClass}>> ${log}</div>`;
      })
      .join("");

    consoleDiv.scrollTop = consoleDiv.scrollHeight;

    // Render AI Hints
    renderAIResponse(data, hintDiv);
  } catch (err) {
    consoleDiv.innerHTML += `<div class="log-entry error" style="color:#f85149">> Connection Error: Backend unreachable.</div>`;
    showToast("Failed to submit code.", "error");
    hintDiv.innerHTML = `<div style="padding:15px; color:#f85149">Failed to get AI response.</div>`;
  } finally {
    runBtn.disabled = false;
    runBtn.style.opacity = "1";
  }
}

function renderAIResponse(data, container) {
  const statusColor = data.status === "Success" ? "#238636" : "#f85149";

  let html = `
    <div style="border-left: 3px solid ${statusColor}; padding-left: 12px; margin-bottom: 15px;">
        <strong style="color:${statusColor}; font-size:14px; letter-spacing:0.5px">[${data.status}]</strong>
        <p style="margin-top:8px; color:#c9d1d9; font-size:13px; line-height:1.5">${data.hint}</p>
    </div>
  `;

  if (data.citation) {
    html += `
        <div style="font-size:11px; color:#8b949e; border-top:1px solid #30363d; padding-top:8px; margin-bottom:10px;">
            <strong>Reference:</strong> ${data.citation}
        </div>`;
  }

  if (data.patch) {
    const escapedPatch = data.patch
      .replace(/`/g, "\\`")
      .replace(/"/g, "&quot;");
    html += `
        <div style="background:#0d1117; padding:10px; border-radius:4px; border:1px solid #30363d; margin-top:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;">
                <h4 style="font-size:12px; color:#58a6ff; margin:0;">Suggested Fix:</h4>
                <button 
                    onclick="applyPatch(\`${escapedPatch}\`)"
                    style="background:#238636; border:none; color:white; font-size:10px; padding:2px 6px; border-radius:3px; cursor:pointer;"
                >Apply Fix</button>
            </div>
            <pre style="margin:0; font-size:11px; color:#a5d6ff; overflow-x:auto; font-family:'Fira Code', monospace;">${data.patch}</pre>
        </div>`;
  }

  container.innerHTML = html;
}

// Global function for the Apply Fix button
window.applyPatch = function (patchCode) {
  if (
    confirm(
      "Are you sure you want to replace your current code with this suggested fix?"
    )
  ) {
    editor.setValue(patchCode);
    showToast("Patch applied successfully!", "success");
  }
};
