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

To prevent unnecessary LLM token usage and API costs, the system uses **Google Sheets as a persistent database** with strict API rate-limit protections.

- **Shift-Left Duplicate Checking:** Before passing any manual or automated job to the LLM, the system queries the memory grid to instantly drop URLs or IDs processed in previous runs.
- **The Safety Valve:** The system enforces a strict 30-job daily insertion limit via bulk-row updates to prevent database bloat and Google Sheets API quota crashes.
- **Quality Gatekeeper:** Only jobs scoring an 80/100 or higher are saved to the CRM and sent via Telegram.

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

## ✨ Core Features

- **🕵️ Multi-Source Aggregation:** Pulls high-signal AI startup roles from _Wellfound_, _Y Combinator (Work at a Startup)_, _RemoteOK_, and _LinkedIn_.
- **🧠 Intelligent Semantic Scoring:** Gemini 2.0 acts as a technical recruiter, scoring jobs (0-100) based on tech stack alignment. It calculates missing gaps, strictly rejects irrelevant roles, and provides strategic application advice.
- **✍️ Auto-Drafting:** Generates highly personalized cover letters and freelance proposals ready for immediate submission, accessible directly from the UI.
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
git clone https://github.com/pgauin01/hustle-bot.git
cd hustle-bot
pip install -r requirements.txt
```

### 3. Configuration

Set your secrets:
If using .env file:
```json
{
"GOOGLE_API_KEY" = "AIzaSy..."
"TELEGRAM_BOT_TOKEN" = "123456:ABC-DEF..."
"TELEGRAM_CHAT_ID" = "987654321"
"GOOGLE_SHEET_URL" = "https://docs.google.com/spreadsheets/d/..."
}
```

If using Streamlit Secrets (`.streamlit/secrets.toml`):
```toml
GOOGLE_API_KEY = "AIzaSy..."
TELEGRAM_BOT_TOKEN = "123456:ABC-DEF..."
TELEGRAM_CHAT_ID = "987654321"
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/..."
GOOGLE_CREDENTIALS_JSON = '''

'''
```

## Local Google Credentials:
Place a credentials.json file (your Google Service Account JSON) directly in the root directory of the project. This file is already tracked in .gitignore to keep your credentials safe from accidental public commits.
```json
{
  "type": "service_account",
  "project_id": "hustle-bot-sheets",
  "private_key_id": "your-private-key",
  "private_key": "-----BEGIN PRIVATE KEY-----your-key-----END PRIVATE KEY-----\n",
  "client_email": "sheet email",
  "client_id": "your_client_id",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/sheet-logger%40hustle-bot-sheets.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}
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
