import os
import time  # <--- Added for throttling
from langgraph.graph import StateGraph, END
from .state import JobState
from ..models.job import Job
from ..utils.cleaning import clean_html
from ..llm.scoring import score_jobs_with_resume
from ..utils.google_sheets import log_jobs_to_sheet
from ..utils.history import load_history
from ..notifications.telegram import send_telegram_alert 

# --- PLATFORM IMPORTS ---
from ..platforms.remoteok import fetch_from_remoteok
from ..platforms.weworkremotely import fetch_weworkremotely
from ..platforms.upwork import fetch_upwork_api
from ..platforms.freelancer import fetch_freelancer_api
from ..platforms.linkedin import fetch_linkedin_jobs
from dotenv import load_dotenv  

load_dotenv()


# --- 1. Fetchers ---
def fetch_remoteok(state: JobState):
    if "RemoteOK" not in state.get("selected_platforms", []): return {"raw_results": []}
    query = state.get("search_query", "python")
    print(f"🌍 Fetching RemoteOK for '{query}'...")
    try:
        raw = fetch_from_remoteok(tag=query)
        return {"raw_results": [{"source": "remoteok", "payload": j} for j in raw]}
    except Exception as e:
        print(f"❌ RemoteOK Failed: {e}")
        return {"raw_results": []}

def fetch_wwr(state: JobState):
    existing = state.get("raw_results", [])
    if "WeWorkRemotely" not in state.get("selected_platforms", []): return {"raw_results": existing}
    print("🌍 Fetching WeWorkRemotely...")
    try:
        raw = fetch_weworkremotely()
        new = [{"source": "wwr", "payload": j} for j in raw]
        return {"raw_results": existing + new}
    except Exception: return {"raw_results": existing}

def fetch_upwork(state: JobState):
    existing = state.get("raw_results", [])
    if "Upwork" not in state.get("selected_platforms", []): return {"raw_results": existing}
    query = state.get("search_query", "python")
    print(f"🌍 Fetching Upwork RSS for '{query}'...")
    try:
        raw = fetch_upwork_api(query)
        new = [{"source": "upwork", "payload": j} for j in raw]
        return {"raw_results": existing + new}
    except Exception: return {"raw_results": existing}

def fetch_freelancer(state: JobState):
    existing = state.get("raw_results", [])
    if "Freelancer" not in state.get("selected_platforms", []): return {"raw_results": existing}
    print(f"🦅 Fetching Freelancer...")
    try:
        res = fetch_freelancer_api(state)
        return {"raw_results": existing + res.get("raw_results", [])}
    except Exception: return {"raw_results": existing}

def fetch_linkedin(state: JobState):
    existing = state.get("raw_results", [])
    if "LinkedIn" not in state.get("selected_platforms", []): return {"raw_results": existing}
    query = state.get("search_query", "python")
    print(f"👔 Fetching LinkedIn (Guest Mode) for '{query}'...")
    new_jobs = []
    for loc in ["India", "Remote"]:
        try:
            raw = fetch_linkedin_jobs(query=query, location=loc)
            new_jobs.extend([{"source": "linkedin", "payload": j} for j in raw])
        except: pass
    return {"raw_results": existing + new_jobs}

# --- 2. Normalizer ---
def normalize_data(state: JobState):
    raw_results = state.get("raw_results", [])
    normalized_jobs = []
    seen_history = load_history()
    seen_urls = set()
    
    print(f"🔄 Normalizing {len(raw_results)} jobs...")
    
    for item in raw_results:
        source = item["source"]
        p = item["payload"]
        try:
            job = None
            if source == "remoteok":
                job = Job(id=str(p.get("id", p.get("url"))), platform="remoteok", title=p.get("position"), company=p.get("company"), description=clean_html(p.get("description")), url=p.get("url"), budget_min=float(p.get("salary_min") or 0), budget_max=float(p.get("salary_max") or 0), is_remote=True)
            elif source == "upwork":
                job = Job(id=p.get("id"), platform="upwork", title=p.get("title"), company="Upwork Client", description=clean_html(p.get("description")), url=p.get("link"), budget_min=float(p.get("budget_min") or 0), budget_max=float(p.get("budget_max") or 0))
            elif source == "wwr":
                job = Job(id=p.get("id"), platform="weworkremotely", title=p.get("title"), company=p.get("company"), description=clean_html(p.get("description")), url=p.get("link"), budget_min=0.0, budget_max=0.0)
            elif source == "freelancer":
                job = Job(id=str(p.get("id")), platform="freelancer", title=p.get("title"), company="Freelancer Client", description=p.get("description"), url=p.get("url"), budget_min=float(p.get("budget_min") or 0), budget_max=float(p.get("budget_max") or 0))
            elif source == "linkedin":
                job = Job(id=p.get("id"), platform="linkedin", title=p.get("title"), company=p.get("company"), description=p.get("description"), url=p.get("url"), budget_min=0.0, budget_max=0.0)

            if job:
                if job.id in seen_history or job.url in seen_history: continue 
                if job.url in seen_urls: continue
                seen_urls.add(job.url)
                normalized_jobs.append(job)
        except Exception: continue

    print(f"✅ Normalized {len(normalized_jobs)} unique jobs.")
    return {"normalized_jobs": normalized_jobs}

# --- 3. Scorer ---
def score_jobs(state: JobState):
    normalized = state.get("normalized_jobs", [])
    resume_path = "profile.md"
    resume_text = "Generic Profile"
    
    if os.path.exists(resume_path):
        with open(resume_path, "r", encoding="utf-8") as f:
            resume_text = f.read()

    from ..utils.filtering import strict_keyword_filter 
    must_haves = state.get("must_have_keywords", [])
    
    # 1. PULL IN OUR SEEN IDs
    seen_ids = state.get("seen_job_ids", []) 

    if not normalized: return {"filtered_jobs": []}

    # 2. DEDUPLICATE: Filter out jobs we have already saved before doing heavy processing
    unique_jobs = [j for j in normalized if str(j.id) not in seen_ids]
    
    if not unique_jobs: 
        print("All found jobs were duplicates. Skipping scoring.")
        return {"filtered_jobs": []}

    # 3. FILTER & SCORE
    technically_qualified = strict_keyword_filter(unique_jobs, must_haves)
    if not technically_qualified: return {"filtered_jobs": []}

    scored = score_jobs_with_resume(technically_qualified, resume_text)
    
    # 4. SORT BY SCORE & KEEP TOP 3
    # Sort from highest relevance_score to lowest
    scored.sort(key=lambda x: getattr(x, "relevance_score", 0), reverse=True)
    
    # Slice the list to only keep the first 5
    top_5_jobs = scored[:5]

    return {"filtered_jobs": top_5_jobs}

# --- 4. LOGGER (RUNS FIRST) ---
def log_results_node(state: JobState):
    top_jobs = state.get("filtered_jobs", [])
    sheet_url = os.getenv("GOOGLE_SHEET_URL")
    
    if not sheet_url or not top_jobs: return {}

    # FILTER: Only log jobs with Score >= 80
    worthy_jobs = [j for j in top_jobs if j.relevance_score >= 80]
    
    if worthy_jobs:
        print(f"📝 Logging {len(worthy_jobs)} high-quality jobs (80+) to Google Sheets...")
        try:
            log_jobs_to_sheet(worthy_jobs, sheet_url)
            print("✅ Successfully logged to Google Sheets.")
        except Exception as e:
            print(f"❌ Sheet Logging Error: {e}")
    else:
        print("ℹ️ No jobs scored >= 80 to log.")
            
    return {}

# --- 5. NOTIFIER (RUNS SECOND - CAPPED) ---
def notify_user(state):
    all_jobs = state.get("filtered_jobs", [])
    
    # FILTER: High Value only
    high_value = [j for j in all_jobs if getattr(j, "relevance_score", 0) >= 80]
    
    # SORT: Best matches first
    high_value.sort(key=lambda x: getattr(x, "relevance_score", 0), reverse=True)
    
    # CAP: Top 5 Only (To match our Executive Summary strategy)
    top_picks = high_value[:5]
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if token and chat_id and top_picks:
        print(f"🚀 Sending Telegram alerts for Top {len(top_picks)} jobs...")
        for i, job in enumerate(top_picks):
            try:
                # 🛑 THE FIX: Pass the whole 'job' object instead of 5 separate arguments
                send_telegram_alert(job)
                
                # THROTTLE: Sleep 1s to prevent timeout/ban from Telegram
                if i < len(top_picks) - 1: 
                    time.sleep(1) 
            except Exception as e:
                print(f"⚠️ Telegram Error for {getattr(job, 'title', 'Unknown')}: {e}")
    
    return {}
# --- 6. Graph Construction ---
def create_graph():
    workflow = StateGraph(JobState)

    workflow.add_node("remoteok_fetcher", fetch_remoteok)
    workflow.add_node("wwr_fetcher", fetch_wwr)
    workflow.add_node("upwork_fetcher", fetch_upwork)
    workflow.add_node("freelancer_fetcher", fetch_freelancer) 
    workflow.add_node("linkedin_fetcher", fetch_linkedin)
    
    workflow.add_node("normalizer", normalize_data)
    workflow.add_node("scorer", score_jobs)
    workflow.add_node("logger", log_results_node) # ✅ Logger is now a node
    workflow.add_node("notifier", notify_user)

    # Flow
    workflow.set_entry_point("remoteok_fetcher") 
    workflow.add_edge("remoteok_fetcher", "wwr_fetcher")
    workflow.add_edge("wwr_fetcher", "upwork_fetcher")   
    workflow.add_edge("upwork_fetcher", "freelancer_fetcher")
    workflow.add_edge("freelancer_fetcher", "linkedin_fetcher")
    workflow.add_edge("linkedin_fetcher", "normalizer") 
    
    workflow.add_edge("normalizer", "scorer")
    
    # ✅ NEW ORDER: Scorer -> Logger -> Notifier -> END
    # This ensures data is saved even if Telegram crashes
    workflow.add_edge("scorer", "logger")
    workflow.add_edge("logger", "notifier")
    workflow.add_edge("notifier", END)      

    return workflow.compile()