🤖 HustleBot: Autonomous AI Job Search Orchestrator

HustleBot is a fully autonomous, production-grade AI agent that manages the entire job search pipeline.

Built with LangGraph and Google Gemini 2.0 Flash, it continuously scrapes job boards, semantically scores opportunities against a master profile, auto-generates tailored career documents, and tracks everything inside a persistent CRM.








🌟 System Architecture & Engineering Highlights

This project treats job hunting as a scalable data pipeline, not a manual activity.

1️⃣ The Orchestrator (Rate-Limit Safe Design)

Job boards heavily rate-limit scraping activity. HustleBot avoids bans using a Time-Based Indexing Scheduler powered by GitHub Actions.

Targets 15 distinct engineering roles

Runs every 96 minutes (1440 minutes ÷ 15 roles)

Executes exactly one role search per run

Achieves 24/7 distributed coverage without triggering platform throttling

This design converts a rate-limit constraint into a deterministic scheduling advantage.

2️⃣ Global Deduplication & Cost Optimization

LLM tokens are expensive. Duplicate scoring is wasteful.

HustleBot uses Google Sheets as a persistent CRM database with strict quota controls.

Shift-Left Deduplication
Drops previously seen URLs before LLM evaluation

Daily Safety Valve
Hard cap of 30 inserts per day via bulk operations

Quality Gatekeeper
Only roles scoring ≥ 80/100 are saved and notified

Result: lower token burn, lower API cost, controlled database growth.

3️⃣ Agentic Workflow (LangGraph DAG)

The core engine runs as a directed acyclic graph (DAG) state machine:

graph LR
    A[Multi-Source Scrapers] --> B[Deduplication Node]
    B --> C{Strict Keyword Filter}
    C -- Pass --> D[Gemini 2.0 Scorer]
    C -- Fail --> X[Discard]
    D -- Score >= 80 --> E[Google Sheets CRM via Bulk Insert]
    D -- Score < 80 --> X
    E --> F[Telegram Executive Summary]

This ensures:

Deterministic execution

Explicit failure paths

Controlled branching

Clean observability

✨ Core Features
🕵️ Multi-Source Aggregation

Pulls job data from:

RemoteOK

WeWorkRemotely

Freelancer

LinkedIn

🧠 Intelligent Semantic Scoring

Gemini 2.0 acts like a technical recruiter:

Scores roles 0–100

Identifies missing skill gaps

Rejects irrelevant roles

Generates strategic application insights

✍️ Auto-Drafting Engine

Generates:

Tailored resumes

Custom cover letters

Freelance proposals

Ready for immediate submission.

📱 Executive Telegram Alerts

Sends formatted HTML summaries including:

High-match indicators

AI reasoning

Direct apply links

📊 Streamlit Command Center

Cloud dashboard for:

Viewing matches

Filtering by score/date

Manual job injection

Tracking application status

🚀 Getting Started
1️⃣ Prerequisites

Python 3.10+

Google Gemini API Key

Telegram Bot Token & Chat ID

Google Service Account JSON (for Sheets access)

2️⃣ Installation
git clone https://github.com/pgauin/hustle-bot.git
cd hustle-bot
pip install -r requirements.txt
3️⃣ Configuration

Set secrets using .streamlit/secrets.toml or a .env file.

Example:

GOOGLE_API_KEY = "AIzaSy..."
TELEGRAM_BOT_TOKEN = "123456:ABC-DEF..."
TELEGRAM_CHAT_ID = "987654321"
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/..."
GOOGLE_CREDENTIALS_JSON = """{ "type": "service_account", ... }"""
4️⃣ Setup Your Master Profile

Edit profile.md.

This file is the AI’s source-of-truth resume.

The system:

Reorders

Filters

Subtracts gaps

It does not hallucinate new skills.

Be detailed.

🖥️ Usage
Option A: Dashboard Mode (Interactive)

Best for manual exploration and CRM management.

streamlit run dashboard.py
Option B: Headless Mode (CLI Automation)

Trigger role-specific runs:

python automate.py --role "Senior Full Stack Engineer"
☁️ Automated Deployment (GitHub Actions Scheduler)

Preconfigured workflow:
.github/workflows/daily_bot.yml

Setup Steps:

Push repository to GitHub

Navigate to:
Settings → Secrets and variables → Actions

Add:

GOOGLE_API_KEY

TELEGRAM_BOT_TOKEN

TELEGRAM_CHAT_ID

GOOGLE_SHEET_URL

GOOGLE_CREDENTIALS_JSON

Scheduler runs automatically every 96 minutes

You now have a background AI recruiter working continuously.

📂 Project Structure
hustle-bot/
├── .github/workflows/      # 96-minute scheduler
├── generated_resumes/      # AI-generated markdown resumes
├── src/
│   ├── graph/              # LangGraph workflow definitions
│   ├── llm/                # Gemini scoring & drafting
│   ├── models/             # Job schema definitions
│   ├── platforms/          # Scrapers & integrations
│   ├── notifications/      # Telegram alert formatting
│   └── utils/              # Sheets persistence & helpers
├── dashboard.py            # Streamlit UI
├── automate.py             # Headless orchestrator
├── profile.md              # Master resume source
└── requirements.txt        # Dependencies
🛡️ License

MIT License.

Built to automate the hustle.

This version will render:

Mermaid diagram correctly

Markdown sections cleanly

No lexical errors

No nested fence conflicts
