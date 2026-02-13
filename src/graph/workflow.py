import os
from langgraph.graph import StateGraph, END
from .state import JobState
from ..models.job import Job
from ..utils.cleaning import clean_html
from ..utils.google_sheets import log_jobs_to_sheet
from ..utils.history import load_history
from ..notifications.telegram import send_telegram_alert 

# --- PLATFORM IMPORTS ---
from ..platforms.remoteok import fetch_from_remoteok
from ..platforms.weworkremotely import fetch_weworkremotely
from ..platforms.upwork import fetch_upwork_api
from ..platforms.freelancer import fetch_freelancer_api
from ..platforms.linkedin import fetch_linkedin_jobs  
from ..llm.scoring import score_jobs_with_resume

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

# --- NEW LINKEDIN NODE ---
def fetch_linkedin(state: JobState):
    existing = state.get("raw_results", [])
    
    # Check if selected
    if "LinkedIn" not in state.get("selected_platforms", []):
        print("⏭️ Skipping LinkedIn (Not selected)")
        return {"raw_results": existing}

    query = state.get("search_query", "python")
    print(f"👔 Fetching LinkedIn (Guest Mode) for '{query}'...")
    
    new_jobs = []
    # --- LOCATION FILTER ---
    # We search twice: Once for "India", Once for "Remote"
    target_locations = ["India", "Remote"]
    
    for loc in target_locations:
        try:
            raw_jobs = fetch_linkedin_jobs(query=query, location=loc)
            # Tag the source clearly
            new_batch = [{"source": "linkedin", "payload": j} for j in raw_jobs]
            new_jobs.extend(new_batch)
            print(f"   ✅ Found {len(new_batch)} jobs in '{loc}'.")
        except Exception as e:
            print(f"   ❌ Failed to fetch '{loc}': {e}")

    return {"raw_results": existing + new_jobs}

# --- 2. Normalizer (Updated for LinkedIn) ---
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
                job = Job(id=str(p.get("id", p.get("url"))), platform="remoteok", title=p.get("position"), company=p.get("company"), description=clean_html(p.get("description")), url=p.get("url"), budget_min=float(p.get("salary_min") or 0), budget_max=float(p.get("salary_max") or 0), skills=p.get("tags"), posted_at=p.get("date"), location=p.get("location"), is_remote=True)
            elif source == "upwork":
                job = Job(id=p.get("id"), platform="upwork", title=p.get("title"), company="Upwork Client", description=clean_html(p.get("description")), url=p.get("link"), budget_min=float(p.get("budget_min") or 0), budget_max=float(p.get("budget_max") or 0), location=p.get("location"), skills=p.get("skills"), posted_at=p.get("published"))
            elif source == "wwr":
                job = Job(id=p.get("id"), platform="weworkremotely", title=p.get("title"), company=p.get("company"), description=clean_html(p.get("description")), url=p.get("link"), budget_min=0.0, budget_max=0.0, skills=[], posted_at=p.get("published"))
            elif source == "freelancer":
                job = Job(id=str(p.get("id")), platform="freelancer", title=p.get("title"), company="Freelancer Client", description=p.get("description"), url=p.get("url"), budget_min=float(p.get("budget_min") or 0), budget_max=float(p.get("budget_max") or 0))
            
            # --- LINKEDIN MAPPING ---
            elif source == "linkedin":
                job = Job(
                    id=p.get("id"),
                    platform="linkedin",
                    title=p.get("title"),
                    company=p.get("company"),
                    description=p.get("description"), # Note: LinkedIn Guest API doesn't give full description
                    url=p.get("url"),
                    budget_min=0.0, 
                    budget_max=0.0,
                    location=p.get("location"),
                    posted_at=p.get("date")
                )

            if job:
                if job.id in seen_history or job.url in seen_history: continue 
                if job.url in seen_urls: continue
                seen_urls.add(job.url)
                normalized_jobs.append(job)
        except Exception: continue

    print(f"✅ Normalized {len(normalized_jobs)} unique jobs.")
    return {"normalized_jobs": normalized_jobs}

# --- 3. Scorer (Resume-Aware) ---
def score_jobs(state: JobState):
    normalized = state.get("normalized_jobs", [])
    
    # Load Resume
    resume_path = "profile.md"
    if not os.path.exists(resume_path):
        print("⚠️ profile.md not found! Using Keyword Search only.")
        # Fallback to old logic or return empty
        return {"filtered_jobs": normalized} # Just return all without scoring if no resume
        
    with open(resume_path, "r", encoding="utf-8") as f:
        resume_text = f.read()

    # Apply Basic Keyword Filter first (Cheap Filter)
    from ..utils.filtering import strict_keyword_filter 
    must_haves = state.get("must_have_keywords", [])
    
    if not normalized: return {"filtered_jobs": []}

    # 1. Hard Filter (Must contain "Python")
    technically_qualified = strict_keyword_filter(normalized, must_haves)
    if not technically_qualified: return {"filtered_jobs": []}

    # 2. AI Resume Analysis (Deep Filter)
    scored = score_jobs_with_resume(technically_qualified, resume_text)
    
    return {"filtered_jobs": scored}

# --- 4. Notifier ---
def notify_user(state: JobState):
    all_jobs = state.get("filtered_jobs", [])
    high_value = [j for j in all_jobs if j.relevance_score >= 75]
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id or not high_value: return {}
    for job in high_value:
        try: send_telegram_alert(job.title, job.url, job.relevance_score, job.reasoning, "[View in Dashboard]")
        except: pass
    return {}

# --- 5. Logger ---
def log_results_node(state: JobState):
    top_jobs = state.get("filtered_jobs", [])
    sheet_url = os.getenv("GOOGLE_SHEET_URL")
    if not sheet_url: return {}
    worthy = [j for j in top_jobs if j.relevance_score > 50]
    if worthy:
        try: log_jobs_to_sheet(worthy, sheet_url)
        except: pass
    return {}


# --- 6. Graph ---
def create_graph():
    workflow = StateGraph(JobState)
    workflow.add_node("remoteok_fetcher", fetch_remoteok)
    workflow.add_node("wwr_fetcher", fetch_wwr)
    workflow.add_node("upwork_fetcher", fetch_upwork)
    workflow.add_node("freelancer_fetcher", fetch_freelancer) 
    workflow.add_node("linkedin_fetcher", fetch_linkedin) # <--- ADD NODE
    
    workflow.add_node("normalizer", normalize_data)
    workflow.add_node("scorer", score_jobs)
    workflow.add_node("notifier", notify_user)
    workflow.add_node("logger", log_results_node)

    # Simple sequential flow
    workflow.set_entry_point("remoteok_fetcher") 
    workflow.add_edge("remoteok_fetcher", "wwr_fetcher")
    workflow.add_edge("wwr_fetcher", "upwork_fetcher")   
    workflow.add_edge("upwork_fetcher", "freelancer_fetcher")
    workflow.add_edge("freelancer_fetcher", "linkedin_fetcher") # <--- LINK NEW NODE
    workflow.add_edge("linkedin_fetcher", "normalizer")         # <--- LINK TO NORMALIZER
    
    workflow.add_edge("normalizer", "scorer")
    workflow.add_edge("scorer", "notifier")
    workflow.add_edge("notifier", "logger")
    workflow.add_edge("logger", END)      

    return workflow.compile()