import os
from langgraph.graph import StateGraph, END
from .state import JobState
from ..models.job import Job
from ..utils.cleaning import clean_html
from ..llm.scoring import score_jobs_with_llm
from ..llm.proposal import generate_proposals
from ..utils.filtering import strict_keyword_filter
from ..notifications.telegram import send_telegram_alert
from ..utils.google_sheets import log_jobs_to_sheet
from ..llm.resume_tailor import tailor_resume
from ..utils.file_manager import save_tailored_resume

# --- IMPORTS (Google Removed) ---
from ..platforms.remoteok import fetch_from_remoteok
from ..platforms.weworkremotely import fetch_weworkremotely
from ..platforms.upwork import fetch_upwork_api
from ..platforms.freelancer import fetch_freelancer_api

# --- 1. Fetchers (Fixed to APPEND data instead of overwriting) ---

def fetch_remoteok(state: JobState):
    query = state.get("search_query", "python")
    print(f"🌍 Fetching RemoteOK for '{query}'...")
    try:
        raw_jobs = fetch_from_remoteok(tag=query)
        # First step: Start the list
        return {"raw_results": [{"source": "remoteok", "payload": j} for j in raw_jobs]}
    except Exception as e:
        print(f"❌ RemoteOK Failed: {e}")
        return {"raw_results": []}

def fetch_wwr(state: JobState):
    print("🌍 Fetching WeWorkRemotely...")
    # Get existing jobs from previous step to avoid overwriting
    existing_jobs = state.get("raw_results", [])
    try:
        raw_jobs = fetch_weworkremotely()
        new_jobs = [{"source": "wwr", "payload": j} for j in raw_jobs]
        return {"raw_results": existing_jobs + new_jobs}
    except Exception as e:
        print(f"❌ WWR Node Failed: {e}")
        return {"raw_results": existing_jobs}

def fetch_upwork(state: JobState):
    query = state.get("search_query", "python")
    print(f"🌍 Fetching Upwork Live Data for '{query}'...")
    existing_jobs = state.get("raw_results", [])
    try:
        raw_jobs = fetch_upwork_api(query)
        new_jobs = [{"source": "upwork", "payload": j} for j in raw_jobs]
        return {"raw_results": existing_jobs + new_jobs}
    except Exception as e:
        print(f"❌ Upwork Node Failed: {e}")
        return {"raw_results": existing_jobs}

def fetch_freelancer(state: JobState):
    # Wrapper to ensure we append, not overwrite
    print(f"🦅 Fetching Freelancer...")
    existing_jobs = state.get("raw_results", [])
    try:
        # Call the API function
        result_dict = fetch_freelancer_api(state)
        new_jobs = result_dict.get("raw_results", [])
        return {"raw_results": existing_jobs + new_jobs}
    except Exception as e:
        print(f"❌ Freelancer Node Failed: {e}")
        return {"raw_results": existing_jobs}

# --- 2. The Normalizer (Google Removed) ---
def normalize_data(state: JobState):
    raw_results = state.get("raw_results", [])
    normalized_jobs = []
    
    print(f"🔄 Normalizing {len(raw_results)} jobs...")

    for item in raw_results:
        source = item["source"]
        payload = item["payload"]
        
        try:
            if source == "remoteok":
                job = Job(
                    id=str(payload.get("id", payload.get("url", ""))),
                    platform="remoteok",
                    title=payload.get("position", "Unknown"),
                    company=payload.get("company", "Unknown"),
                    description=clean_html(payload.get("description", "")),
                    url=payload.get("url", ""),
                    budget_min=float(payload.get("salary_min") or 0),
                    budget_max=float(payload.get("salary_max") or 0),
                    skills=payload.get("tags", []),
                    posted_at=payload.get("date"),
                    location=payload.get("location", "Unknown"), 
                    is_remote=True
                )
                normalized_jobs.append(job)

            elif source == "upwork":
                job = Job(
                    id=payload.get("id") or payload.get("link", ""),
                    platform="upwork",
                    title=payload.get("title", "Unknown"),
                    company="Upwork Client",
                    description=clean_html(payload.get("description", "")),
                    url=payload.get("link", ""),
                    budget_min=float(payload.get("budget_min") or 0.0),
                    budget_max=float(payload.get("budget_max") or 0.0),
                    location=payload.get("location", "Unknown"),
                    skills=payload.get("skills", []),
                    posted_at=payload.get("published")
                )
                normalized_jobs.append(job)

            elif source == "wwr":
                job = Job(
                    id=payload.get("id"),
                    platform="weworkremotely",
                    title=payload.get("title", "Unknown"),
                    company=payload.get("company", "Unknown"),
                    description=clean_html(payload.get("description", "")),
                    url=payload.get("link", ""),
                    budget_min=0.0,
                    budget_max=0.0,
                    skills=[], 
                    posted_at=payload.get("published")
                )
                normalized_jobs.append(job) 
            
            elif source == "freelancer":
                job = Job(
                    id=str(payload.get("id")),
                    platform="freelancer",
                    title=payload.get("title"),
                    company="Freelancer Client",
                    description=payload.get("description"),
                    url=payload.get("url"),
                    budget_min=float(payload.get("budget_min") or 0),
                    budget_max=float(payload.get("budget_max") or 0),
                    currency=payload.get("currency", "USD")
                )
                normalized_jobs.append(job)

        except Exception as e:
            print(f"⚠️ Failed to normalize a {source} job: {e}")
            continue

    print(f"✅ Normalized {len(normalized_jobs)} valid jobs.")
    return {"normalized_jobs": normalized_jobs}

# --- 3. The Scorer ---
def score_jobs(state: JobState):
    normalized = state.get("normalized_jobs", [])
    query = state.get("search_query", "Python Developer")
    must_haves = state.get("must_have_keywords", [])
    
    if not normalized:
        return {"filtered_jobs": []}

    # 1. Hard Filter
    technically_qualified = strict_keyword_filter(normalized, must_haves)
    
    if not technically_qualified:
        print("⚠️ No jobs passed the hard keyword filter.")
        return {"filtered_jobs": []}

    # 2. AI Scoring
    scored = score_jobs_with_llm(technically_qualified, query)
    return {"filtered_jobs": scored}

# --- 4. The Drafter ---
def draft_proposals_node(state: JobState):
    good_jobs = state.get("filtered_jobs", [])
    top_picks = good_jobs[:3]
    if not top_picks:
        return {"proposals": []}
    
    drafts_dict = generate_proposals(top_picks)
    return {"proposals": list(drafts_dict.values())}

# --- 5. Notifier ---
def notify_user(state: JobState):
    top_jobs = state.get("filtered_jobs", [])
    proposals = state.get("proposals", [])
    
    print(f"🔔 Sending alerts for {len(proposals)} jobs...")
    for i, proposal in enumerate(proposals):
        if i < len(top_jobs):
            job = top_jobs[i]
            send_telegram_alert(
                job_title=job.title,
                job_url=job.url,
                score=job.relevance_score,
                reasoning=job.reasoning,
                proposal=proposal
            )
    return {"proposals": proposals}

# --- 6. Logger ---
def log_results_node(state: JobState):
    top_jobs = state.get("filtered_jobs", [])
    sheet_url = os.getenv("GOOGLE_SHEET_URL")
    if top_jobs and sheet_url:
        log_jobs_to_sheet(top_jobs, sheet_url)
    return {}

# --- 7. Resume Tailor ---
def tailor_node(state: JobState):
    top_jobs = state.get("filtered_jobs", [])
    try:
        with open("profile.md", "r", encoding="utf-8") as f:
            base_resume = f.read()
    except:
        print("⚠️ Profile.md not found, skipping resume tailoring.")
        return {}

    tailored_paths = []
    print(f"👔 Checking {len(top_jobs)} jobs for tailoring candidates (Score >= 85)...")
    
    for job in top_jobs:
        if job.relevance_score >= 85:
            print(f"   ✨ Generating resume for: {job.title}...")
            try:
                new_resume = tailor_resume(job, base_resume)
                path = save_tailored_resume(new_resume, job.company, job.title)
                tailored_paths.append(path)
            except Exception as e:
                print(f"   ❌ Failed to generate/save: {e}")

    return {"tailored_resumes": tailored_paths}

# --- 8. Graph Construction ---

def create_graph():
    workflow = StateGraph(JobState)

    # Nodes
    workflow.add_node("remoteok_fetcher", fetch_remoteok)
    workflow.add_node("wwr_fetcher", fetch_wwr)
    workflow.add_node("upwork_fetcher", fetch_upwork)
    workflow.add_node("freelancer_fetcher", fetch_freelancer) # Uses wrapper
    
    workflow.add_node("normalizer", normalize_data)
    workflow.add_node("scorer", score_jobs)
    workflow.add_node("tailor", tailor_node)
    workflow.add_node("drafter", draft_proposals_node)
    workflow.add_node("notifier", notify_user)
    workflow.add_node("logger", log_results_node)

    # Chain: RemoteOK -> WWR -> Upwork -> Freelancer -> Normalizer
    workflow.set_entry_point("remoteok_fetcher") 
    workflow.add_edge("remoteok_fetcher", "wwr_fetcher")
    workflow.add_edge("wwr_fetcher", "upwork_fetcher")   
    workflow.add_edge("upwork_fetcher", "freelancer_fetcher")
    workflow.add_edge("freelancer_fetcher", "normalizer") # No Google
    
    workflow.add_edge("normalizer", "scorer")
    workflow.add_edge("scorer", "tailor")  
    workflow.add_edge("tailor", "drafter")
    workflow.add_edge("drafter", "notifier")
    workflow.add_edge("notifier", "logger")
    workflow.add_edge("logger", END)      

    return workflow.compile()