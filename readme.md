````markdown
# 🤖 HustleBot: Autonomous AI Job Search Orchestrator

**HustleBot** is a fully autonomous, production-grade AI agent that manages the entire job search pipeline. Built with **LangGraph** and **Google Gemini 2.0 Flash**, it continuously scrapes job boards, semantically scores opportunities against a master profile, and auto-generates tailored career documents (Resumes & Cover Letters) while tracking everything in a persistent CRM.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-orange.svg)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini%202.0-8E44AD.svg)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B.svg)

## 🌟 System Architecture & Engineering Highlights

This project was built to solve the inefficiencies of manual job hunting by treating the process as a scalable data pipeline.

### 1. The Orchestrator (Bypassing Rate Limits)

Job boards heavily rate-limit scrapers. To solve this, HustleBot utilizes a **Time-Based Indexing Scheduler** running via GitHub Actions.

- It targets **15 distinct Engineering roles** (e.g., "RAG Engineer", "Full Stack AI Engineer").
- The scheduler wakes up exactly every **96 minutes** (1440 mins / 15 roles), calculates the current UTC time, and executes a search for a single, specific role. This ensures 24/7 coverage without triggering platform bans.

### 2. Global Deduplication & Cost Optimization

To prevent unnecessary LLM token usage and API costs, the system uses **Google Sheets as a persistent database**.

- Before passing raw scraped jobs to the LLM, the graph checks the database and instantly drops jobs that were processed in previous runs.
- The system is capped to only process, log, and notify the user about the **Top 3 absolute best matches** per run.

### 3. Agentic Workflow (LangGraph)

The core logic operates as a directed acyclic graph (DAG) state machine:

```mermaid
graph LR
    A[Multi-Source Scrapers] --> B[Deduplication Node]
    B --> C{Strict Keyword Filter}
    C -- Pass --> D[Gemini 2.0 Scorer]
    C -- Fail --> End
    D -- Score > 80 --> E[Google Sheets CRM]
    E --> F[Telegram Exec Summary]
```
````

---

## ✨ Core Features

- **🕵️ Multi-Source Aggregation:** Pulls data from _RemoteOK_, _WeWorkRemotely_, _Upwork_, _Freelancer_, and _LinkedIn_.
- **🧠 Intelligent Semantic Scoring:** Gemini 2.0 acts as a technical recruiter, scoring jobs (0-100) based on tech stack alignment. It calculates missing gaps, strictly rejects irrelevant roles, and provides strategic application advice.
- **👔 Dynamic Resume Tailoring:** Completely rewrites your master `profile.md` for _every_ specific high-quality match. It re-orders skills to match the JD, optimizes ATS keywords, and outputs a clean Markdown file.
- **✍️ Auto-Drafting:** Generates personalized cover letters and freelance proposals ready for immediate submission.
- **📱 Executive Summary Alerts:** Sends highly formatted HTML Telegram notifications featuring unicorn/high-match badges, AI reasoning, and "One-Click Apply" links.
- **📊 Streamlit Command Center:** A fully deployed cloud dashboard to view matches, filter by score/date, manually inject jobs, and track application statuses.

---

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.10+
- Google Gemini API Key
- Telegram Bot Token & Chat ID
- Google Service Account JSON (for Sheets)

### 2. Installation

```bash
git clone [https://github.com/pgauin/hustle-bot.git](https://github.com/pgauin/hustle-bot.git)
cd hustle-bot
pip install -r requirements.txt

```

### 3. Configuration

Set your secrets securely using Streamlit Secrets (`.streamlit/secrets.toml`) or a local `.env` file:

```toml
GOOGLE_API_KEY = "AIzaSy..."
TELEGRAM_BOT_TOKEN = "123456:ABC-DEF..."
TELEGRAM_CHAT_ID = "987654321"
GOOGLE_SHEET_URL = "[https://docs.google.com/spreadsheets/d/](https://docs.google.com/spreadsheets/d/)..."
GOOGLE_CREDENTIALS_JSON = """{ "type": "service_account", ... }"""

```

### 4. Setup Your Profile

Edit the `profile.md` file in the root directory. This serves as the "Master Source" for the AI. _Tip: Be detailed! The AI subtracts/re-orders from this file, it doesn't invent new skills._

---

## 🖥️ Usage

**Option A: The Dashboard (Interactive)**
Best for manual searches, downloading tailored resumes, and reviewing your CRM.

```bash
streamlit run dashboard.py

```

**Option B: Headless Mode (CLI)**
Trigger a local headless run targeting a specific role using the orchestrator:

```bash
python automate.py --role "Senior Full Stack Engineer"

```

---

## ☁️ Deployment (GitHub Actions)

This repo includes a pre-configured workflow for the 96-minute scheduler (`.github/workflows/daily_bot.yml`).

1. Push code to GitHub.
2. Go to **Settings > Secrets and variables > Actions**.
3. Add your secrets (`GOOGLE_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GOOGLE_SHEET_URL`, `GOOGLE_CREDENTIALS_JSON`).
4. The bot will now run automatically in the background, pinging your Telegram throughout the day with the Top 3 matches per role.

---

## 📂 Project Structure

```text
hustle-bot/
├── .github/workflows/   # CI/CD for the 96-minute time-based scheduler
├── generated_resumes/   # Ephemeral storage for AI-tailored Markdown resumes
├── src/
│   ├── graph/           # LangGraph State & Workflow definitions
│   ├── llm/             # Gemini integrations (Scoring, Tailoring, Proposals)
│   ├── models/          # Data Classes (Job schema)
│   ├── platforms/       # Web Scrapers & API integrations
│   ├── notifications/   # HTML-formatted Telegram alerts
│   └── utils/           # Google Sheets persistence & DataFrame handling
├── dashboard.py         # Streamlit Cloud UI
├── automate.py          # Headless orchestrator & CLI entry point
├── profile.md           # The Master Resume data source
└── requirements.txt     # Python Dependencies

```

## 🛡️ License

MIT License. Built to automate the hustle.

```

```
