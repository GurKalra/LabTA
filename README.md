# LabTA: Autonomous AI Lab Assistant

## 🚀 Deployments

**Student Portal (Frontend):** [LabTA](https://lab-ta.vercel.app)
**API Server (Backend):** Hosted on GitHub Codespaces (Containerized Infrastructure)

---

## 🏆 AI IGNITE 2025: Innovation at Scale

AI IGNITE 2025, organized by **Sri Manakula Vinayagar Engineering College (SMVEC)** and **LLM at Scale AI**, is a national-level Gen-AI competition enabling innovators to explore the transformative power of artificial intelligence.

Participants leverage **large language models, generative agents, and multimodal systems** to build practical, future-ready solutions. Supported by industry-academic collaboration, AI Ignite turns ideas into impact and **LabTA** is our flagship solution to build an intelligent, responsible, and scalable future for technical education.

---

## 👥 The Team (Github Accounts included)

- **Gurvansh Singh Kalra (@GurKalra)**
- **Monalisa Bhattacharjee (@Moonnn15)**
- **Krishna Shukla (@Krish02185)**
- **Sreejita Das (@Sreejita)**

---

## 🚩 The Problem Statement: The Programming Lab Bottleneck

Programming labs are the backbone of hands-on learning, but as class sizes grow, a **Lab Scalability Crisis** emerges.

A single TA may support **50+ students simultaneously**, leading to systemic challenges:

**Instructional Bottlenecks**
Students lose up to **70% of lab time** waiting in queues for minor syntax or runtime issues.

**Pedagogical Fatigue**
Under pressure, TAs resort to spoon-feeding fixes instead of teaching debugging.

**The Data Void**
Instructors have **no real-time insights** into which concepts students struggle with.

The result?
Delays, shallow learning, and zero visibility into class-wide problem trends.

---

## 💡 Our Solution: The LabTA Ecosystem

LabTA is an **autonomous, code-aware AI Teaching Assistant**. Not just a chatbot, but a **Closed-Loop Execution & Diagnosis System**.

It executes student code inside a secure sandbox, analyzes failures, and provides structured mentorship in real time.

### What LabTA Does

- **Secure Sandbox Execution**
  Code is compiled and executed inside an isolated Docker container.

- **Hierarchical Diagnosis**
  Distinguishes **Syntax, Runtime, and Logic errors** with precision.

- **Pedagogical Mentorship**
  Provides **scaffolded hints**, not direct answers — supporting real learning.

- **Surgical Code Patching**
  When students are stuck, LabTA suggests **git-diff-based patches** to guide recovery without skipping the learning process.

---

## ⚙️ Architecture: Modular Orchestration

LabTA follows a **modular, decoupled architecture** designed for scalability, security, and reliability.

### 1. Frontend — The Navigator

**Tech Stack:** HTML5, CSS3, Vanilla JS (ES6+), CodeMirror 5
Acts as the student mission control with a high-focus coding IDE.

Key capability:
The **Apply Fix Engine** parses backend-generated git-diff patches and applies them selectively to the editor buffer.

---

### 2. Backend — The Orchestrator

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn
Coordinates sessions, persists drafts, and manages logic flow.

**Intelligent routing ensures AI calls are used only when necessary.**

---

### 3. Sandbox — The Engine

**Tech Stack:** Docker, Python Subprocess API

Execution Process:

- Spawns an isolated container (`lab-ta-runner`)
- Mounts student code + hidden tests
- Enforces **256MB RAM, 0.5 CPU, 5s timeout**
- Captures logs
- Destroys container instantly after execution

---

### 4. Agent — The Brain

**Tech Stack:** Google Gemini 2.5 Flash, RAG

Capabilities:

- **Priority-aware error analysis** via `error_dictionary.json`
- **Context-aligned debugging hints** using `lab_manual_index.json`

Students receive guidance grounded in **their actual course material**.

---

## 📂 Project Structure

```
LabTA/
├── backend/                # The Orchestration Layer
│   ├── app.py              # Main FastAPI Entry Point & Routing
│   ├── agent.py            # AI Reasoning, RAG & Patch Logic
│   ├── sandbox.py          # Docker Life-cycle & Sandbox Execution
│   └── diagnostics.py      # Multi-language Error Prioritization
├── frontend/               # The Presentation Layer
│   ├── index.html          # Professional Landing Portal (Vercel Root)
│   ├── selection.html      # Problem Navigator & Card System
│   ├── problem.html        # Integrated AI-IDE with Diff Support
│   ├── dashboard.html      # Teacher Analytics & Heatmap Dashboard
│   ├── script.js           # API Orchestration & Diff Parsing Engine
│   └── style.css           # Matrix-themed Dark UI Framework
├── data/                   # The Knowledge Layer
│   ├── problems.json       # Challenge Database & Hidden Tests
│   ├── error_dictionary.json # Weighted Error Priority Rules
│   ├── lab_manual_index.json # Knowledge Base for RAG Hints
│   └── sessions.json       # Persistent Student Analytics
├── runner/                 # The Infrastructure Layer
│   └── Dockerfile          # Security-Hardened Linux Sandbox
├── requirements.txt        # Backend Python Manifest
└── README.md               # Extensive Project Documentation
```

---

## 🛠️ Tech Stack Specification

```
|-------------------------|-------------------------|--------------------------------------------|
|        Category         |        Technology       |           Implementation Detail            |
|-------------------------|-------------------------|--------------------------------------------|
| Artificial Intelligence | Google Gemini 2.5 Flash | Ultra-low latency, high-accuracy diagnosis |
|-------------------------|-------------------------|--------------------------------------------|
|       AI Strategy       |        RAG & CoT        | Course-grounded retrieval hints            |
|-------------------------|-------------------------|--------------------------------------------|
|       Backend API       |         FastAPI         | Async high-concurrency architecture        |
|-------------------------|-------------------------|--------------------------------------------|
|     Infrastructure      |         Docker          | Full code isolation via containers         |
|-------------------------|-------------------------|--------------------------------------------|
|      Frontend IDE       |       CodeMirror 5      | Multi-language syntax editor               |
|-------------------------|-------------------------|--------------------------------------------|
|    Data Visualization   |        Chart.js         | Real-time learning analytics               |
|-------------------------|-------------------------|--------------------------------------------|
|         Hosting         |    Vercel + Codespaces  | Edge frontend + cloud backend              |
|-------------------------|-------------------------|--------------------------------------------|
```

---

## 🛡️ Technical Standards & Compliance

- Modular separation across **logic, UI, data, and infra**
- Open-source **interoperable REST JSON APIs**
- Strict execution limits to prevent abuse
- Fully audit-tracked via Git

---

## 📈 Impact Assessment

**Instructor Efficiency:** Cuts repetitive TA effort by ~70%
**Student Growth:** Encourages debugging instead of copying answers
**Teaching Insight:** Real-time heatmaps reveal learning gaps

**Future Scaling**

- Kubernetes-ready container runners
- Language-agnostic architecture
- Planned LMS integration (LTI)

---

## 🚀 How to Run Locally

### 1️⃣ Build the Secure Sandbox

```bash
docker build -t lab-ta-runner -f runner/Dockerfile .
```

### 2️⃣ Set Up the Python Backend

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scriptsctivate

pip install -r requirements.txt
```

### 3️⃣ Configure the AI Agent

```bash
echo "LLM_API_KEY=your_google_gemini_api_key_here" > .env
```

### 4️⃣ Start the Backend Server

```bash
python -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

### 5️⃣ Launch the Student Portal

```bash
xdg-open frontend/index.html   # Linux
open frontend/index.html       # macOS
start frontend/index.html      # Windows
```
