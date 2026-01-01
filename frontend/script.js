/* CONFIGURATION */
const API_BASE =
  "https://super-duper-space-dollop-749rxgq97q72x9j9-8000.app.github.dev/";

let USER_ID = localStorage.getItem("labta_user_id");
if (!USER_ID) {
  USER_ID = "student_" + Math.floor(Math.random() * 9000 + 1000);
  localStorage.setItem("labta_user_id", USER_ID);
}

const urlParams = new URLSearchParams(window.location.search);
const PROBLEM_ID = urlParams.get("id");
let editor;
let pendingPatchCode = null; // Store patch data while waiting for confirmation

document.addEventListener("DOMContentLoaded", async () => {
  // 1. Initialize CodeMirror
  const textarea = document.getElementById("editor-textarea");
  if (textarea) {
    editor = CodeMirror.fromTextArea(textarea, {
      lineNumbers: true,
      theme: "dracula",
      mode: "python",
      indentUnit: 4,
      autoCloseBrackets: true,
      matchBrackets: true,
      lineWrapping: true,
      viewportMargin: Infinity,
    });
  }

  // 2. Setup UI Components
  setupResizers();
  setupModalLogic(); // <--- NEW: Initialize the popup box

  // 3. Event Listeners
  const saveBtn = document.getElementById("save-btn");
  const runBtn = document.getElementById("run-btn");
  const langSelect = document.getElementById("language-select");

  if (saveBtn) saveBtn.addEventListener("click", handleSave);
  if (runBtn) runBtn.addEventListener("click", handleRun);

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

  // 4. Load Data
  if (PROBLEM_ID) {
    await loadProblemData();
    await loadDraft();
  } else if (window.location.pathname.endsWith("problem.html")) {
    alert("No Problem ID found.");
    window.location.href = "selection.html";
  }
});

/* --- UI: MODAL LOGIC (NEW) --- */
function setupModalLogic() {
  const modal = document.getElementById("custom-modal");
  const confirmBtn = document.getElementById("modal-confirm");
  const cancelBtn = document.getElementById("modal-cancel");

  if (!modal || !confirmBtn || !cancelBtn) return;

  // Cancel Click
  cancelBtn.addEventListener("click", () => {
    modal.classList.add("hidden");
    pendingPatchCode = null;
  });

  // Confirm Click
  confirmBtn.addEventListener("click", () => {
    if (pendingPatchCode) {
      executePatch(pendingPatchCode);
    }
    modal.classList.add("hidden");
    pendingPatchCode = null;
  });

  // Close if clicking outside the box
  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      modal.classList.add("hidden");
    }
  });
}

// Triggered by the "Apply Fix" button in the AI Hint panel
window.applyPatch = function (patchCode) {
  pendingPatchCode = patchCode;
  const modal = document.getElementById("custom-modal");
  if (modal) modal.classList.remove("hidden");
};

/* --- LOGIC: EXECUTING THE PATCH --- */
function executePatch(patchCode) {
  try {
    const patchLines = patchCode.split("\n");
    const headerLine = patchLines.find((l) => l.startsWith("@@"));

    if (!headerLine) {
      showToast("Error: Invalid patch format", "error");
      return;
    }

    const match = headerLine.match(/^@@ -(\d+),(\d+) \+(\d+),(\d+) @@/);
    if (!match) {
      showToast("Error: Could not parse line numbers", "error");
      return;
    }

    const startLine = parseInt(match[1]) - 1;
    const lineCount = parseInt(match[2]);

    const newContentLines = [];
    let headerFound = false;

    for (let line of patchLines) {
      if (line.startsWith("@@")) {
        if (headerFound) break;
        headerFound = true;
        continue;
      }
      if (!headerFound) continue;

      if (line.startsWith(" ")) {
        newContentLines.push(line.substring(1));
      } else if (line.startsWith("+")) {
        newContentLines.push(line.substring(1));
      }
    }

    const from = { line: startLine, ch: 0 };
    const to = { line: startLine + lineCount, ch: 0 };

    let replacementText = newContentLines.join("\n");

    // Ensure newline if inserting mid-file
    if (startLine + lineCount < editor.lineCount()) {
      replacementText += "\n";
    }

    editor.replaceRange(replacementText, from, to);
    showToast("Fix applied successfully!", "success");
  } catch (e) {
    console.error(e);
    showToast("Error applying patch.", "error");
  }
}

/* --- UI: RESIZER LOGIC --- */
function setupResizers() {
  setupSingleResizer("dragLeft", "left-sidebar", (e, startX, startWidth) => {
    return startWidth + (e.clientX - startX);
  });
  setupSingleResizer("dragRight", "right-sidebar", (e, startX, startWidth) => {
    return startWidth + (startX - e.clientX);
  });
}

function setupSingleResizer(resizerId, sidebarId, calculateWidth) {
  const resizer = document.getElementById(resizerId);
  const sidebar = document.getElementById(sidebarId);
  if (!resizer || !sidebar) return;

  let startX = 0;
  let startWidth = 0;

  const onMouseDown = (e) => {
    startX = e.clientX;
    startWidth = sidebar.getBoundingClientRect().width;
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    resizer.classList.add("active");
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
  };

  const onMouseMove = (e) => {
    const newWidth = calculateWidth(e, startX, startWidth);
    if (newWidth > 200 && newWidth < 800) {
      sidebar.style.width = `${newWidth}px`;
    }
  };

  const onMouseUp = () => {
    document.removeEventListener("mousemove", onMouseMove);
    document.removeEventListener("mouseup", onMouseUp);
    resizer.classList.remove("active");
    document.body.style.removeProperty("user-select");
    document.body.style.removeProperty("cursor");
  };

  resizer.addEventListener("mousedown", onMouseDown);
}

/* --- HELPER: TOAST NOTIFICATIONS --- */
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const box = document.createElement("div");
  box.className = `toast-box ${type}`;
  let icon = type === "success" ? "✅" : type === "error" ? "❌" : "ℹ️";

  box.innerHTML = `<span style="font-size:1.2em">${icon}</span><span>${message}</span>`;
  container.appendChild(box);

  setTimeout(() => {
    box.classList.add("fade-out");
    box.addEventListener("animationend", () => {
      if (box.parentNode) box.remove();
    });
  }, 3000);
}

/* --- LOGIC: RENDER AI RESPONSE --- */
function escapeHtml(text) {
  if (!text) return "";
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderAIResponse(data, container) {
  const statusColor = data.status === "Success" ? "#238636" : "#f85149";

  let html = `
    <div style="border-left: 3px solid ${statusColor}; padding-left: 12px; margin-bottom: 15px;">
        <strong style="color:${statusColor};">[${data.status}]</strong>
        <p style="margin-top:8px; color:#c9d1d9; font-size:13px;">${data.hint}</p>
    </div>
  `;

  if (data.citation) {
    html += `<div style="font-size:11px; color:#8b949e; border-top:1px solid #30363d; padding-top:8px; margin-bottom:10px;">
        <strong>Reference:</strong> ${data.citation}
    </div>`;
  }

  if (data.patch) {
    // 1. Process Diff Visuals
    const formattedPatch = data.patch
      .split("\n")
      .map((line) => {
        const safeLine = escapeHtml(line);
        if (line.startsWith("+"))
          return `<span class="diff-add">${safeLine}</span>`;
        if (line.startsWith("-"))
          return `<span class="diff-remove">${safeLine}</span>`;
        if (line.startsWith("@"))
          return `<span class="diff-header">${safeLine}</span>`;
        return safeLine;
      })
      .join("\n");

    // 2. Raw Patch for Button
    const rawPatch = data.patch.replace(/`/g, "\\`").replace(/"/g, "&quot;");

    html += `
        <div style="background:#0d1117; padding:10px; border-radius:4px; border:1px solid #30363d; margin-top:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;">
                <h4 style="font-size:12px; color:#58a6ff; margin:0;">Suggested Fix:</h4>
                <button onclick="applyPatch(\`${rawPatch}\`)"
                    style="background:#238636; border:none; color:white; font-size:10px; padding:2px 6px; border-radius:3px; cursor:pointer;"
                >Apply Fix</button>
            </div>
            <pre style="margin:0; font-size:11px; color:#a5d6ff; overflow-x:auto; font-family:'Fira Code', monospace; line-height:1.5;">${formattedPatch}</pre>
        </div>`;
  }
  container.innerHTML = html;
}

/* --- BACKEND CALLS --- */
async function loadProblemData() {
  try {
    const res = await fetch(`${API_BASE}/problems`);
    const problems = await res.json();
    const p = problems[PROBLEM_ID];
    if (p) {
      document.getElementById("prob-title").innerText = p.title;
      document.getElementById("prob-desc").innerText = p.description;
      document.getElementById("prob-diff").innerText = p.difficulty;
      if (p.sample_cases[0]) {
        document.getElementById("sample-input").innerText =
          p.sample_cases[0].input;
        document.getElementById("sample-output").innerText =
          p.sample_cases[0].output;
      }
    }
  } catch (err) {
    console.error(err);
  }
}

async function loadDraft() {
  try {
    const res = await fetch(`${API_BASE}/draft/${USER_ID}/${PROBLEM_ID}`);
    if (res.ok) {
      const data = await res.json();
      if (data.draft_code) editor.setValue(data.draft_code);
    }
  } catch (e) {}
}

async function handleSave() {
  const btn = document.getElementById("save-btn");
  btn.innerText = "Saving...";
  btn.disabled = true;
  try {
    await fetch(`${API_BASE}/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: USER_ID,
        problem_id: PROBLEM_ID,
        code: editor.getValue(),
      }),
    });
    showToast("Draft saved!", "success");
  } catch (e) {
    showToast("Save failed", "error");
  } finally {
    btn.innerText = "Save Draft";
    btn.disabled = false;
  }
}

async function handleRun() {
  const consoleDiv = document.getElementById("agent-console");
  const hintDiv = document.getElementById("ai-hints");
  const runBtn = document.getElementById("run-btn");

  runBtn.disabled = true;
  consoleDiv.innerHTML = `<div class="log-entry">> Initializing Docker...</div>`;
  hintDiv.innerHTML = `<div style="text-align:center; padding:20px; color:#888;">AI is analyzing...</div>`;

  try {
    const res = await fetch(`${API_BASE}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: USER_ID,
        problem_id: PROBLEM_ID,
        language: document.getElementById("language-select").value,
        code: editor.getValue(),
      }),
    });
    const data = await res.json();

    consoleDiv.innerHTML = data.agent_logs
      .map(
        (log) =>
          `<div class="log-entry" style="color:${
            /error|fail/i.test(log) ? "#f85149" : "#4ade80"
          }">> ${log}</div>`
      )
      .join("");

    renderAIResponse(data, hintDiv);
  } catch (e) {
    consoleDiv.innerHTML += `<div class="log-entry error">> Connection Error</div>`;
  } finally {
    runBtn.disabled = false;
  }
}
