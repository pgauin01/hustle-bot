import os
import json
import time
import schedule
import sys
from datetime import datetime
from src.graph.workflow import create_graph

# --- CONFIGURATION ---
TARGET_ROLE = "Python Developer"
MUST_HAVE_SKILLS = ["Python", "Django", "Remote"]
RUN_TIME = "09:30" 

def load_settings():
    """Smart Loader: Checks JSON first, then falls back to Environment Variables."""
    # 1. Try Local JSON (For when you run it on your laptop)
    if os.path.exists("user_settings.json"):
        print("📂 Loading settings from local JSON...")
        with open("user_settings.json", "r") as f:
            settings = json.load(f)
            if settings.get("api_key"): os.environ["GOOGLE_API_KEY"] = settings["api_key"]
            if settings.get("sheet_url"): os.environ["GOOGLE_SHEET_URL"] = settings["sheet_url"]
            if settings.get("tele_token"): os.environ["TELEGRAM_BOT_TOKEN"] = settings["tele_token"]
            if settings.get("tele_chat"): os.environ["TELEGRAM_CHAT_ID"] = settings["tele_chat"]
        return True
    
    # 2. Try Environment Variables (For GitHub Actions / Cloud)
    elif os.getenv("GOOGLE_API_KEY"):
        print("☁️ Loading settings from Environment Variables...")
        return True
        
    else:
        print("❌ Error: No API Keys found (checked json and env vars).")
        return False

def job_hunt_task():
    print(f"\n🚀 Starting Job Hunt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    initial_state = {
        "search_query": TARGET_ROLE,
        "must_have_keywords": MUST_HAVE_SKILLS,
        "raw_results": [], "normalized_jobs": [], "filtered_jobs": []
    }
    try:
        app = create_graph()
        app.invoke(initial_state)
        print("✅ Job Hunt Finished.")
    except Exception as e:
        print(f"❌ Workflow Crashed: {e}")

if __name__ == "__main__":
    if not load_settings():
        exit(1)

    # --- MODE 1: CLOUD / SINGLE RUN ---
    # Run with: python automate.py --once
    if "--once" in sys.argv:
        print("⚡ Single Run Mode Activated")
        job_hunt_task()
        exit(0)

    # --- MODE 2: LOCAL LOOP ---
    # Run with: python automate.py
    print(f"🤖 HustleBot Loop Mode. Schedule: {RUN_TIME}")
    schedule.every().day.at(RUN_TIME).do(job_hunt_task)
    
    # Run once on startup just to be sure
    job_hunt_task()
    
    while True:
        schedule.run_pending()
        time.sleep(60)