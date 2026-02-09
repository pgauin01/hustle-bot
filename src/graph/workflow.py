import os
from langgraph.graph import StateGraph, END
from .state import JobState
from ..models.job import Job
from ..utils.cleaning import clean_html
from ..platforms.remoteok import fetch_from_remoteok
from ..llm.scoring import score_jobs_with_llm
from ..llm.proposal import generate_proposals
from ..platforms.weworkremotely import fetch_weworkremotely
from ..platforms.upwork import fetch_upwork_api
from ..utils.filtering import strict_keyword_filter
from ..notifications.telegram import send_telegram_alert
from ..utils.google_sheets import log_jobs_to_sheet
from ..llm.resume_tailor import tailor_resume
from ..utils.file_manager import save_tailored_resume
from ..platforms.freelancer import fetch_freelancer_api
from ..platforms.google_jobs import fetch_google_jobs

# --- 1. Fetchers ---

def fetch_remoteok(state: JobState):
    query = state.get("search_query", "python")
    print(f"🌍 Fetching RemoteOK for '{query}'...")
    try:
        raw_jobs = fetch_from_remoteok(tag=query)
        # Wrap in source dict
        return {"raw_results": [{"source": "remoteok", "payload": j} for j in raw_jobs]}
    except Exception as e:
        print(f"❌ RemoteOK Failed: {e}")
        return {"raw_results": []}

def fetch_upwork(state: JobState):
    query = state.get("search_query", "python")
    print(f"🌍 Fetching Upwork Live Data for '{query}'...")
    
    try:
        raw_jobs = fetch_upwork_api(query)
        return {"raw_results": [{"source": "upwork", "payload": j} for j in raw_jobs]}
    except Exception as e:
        print(f"❌ Upwork Node Failed: {e}")
        return {"raw_results": []}

def fetch_wwr(state: JobState):
    print("🌍 Fetching WeWorkRemotely...")
    try:
        raw_jobs = fetch_weworkremotely()
        return {"raw_results": [{"source": "wwr", "payload": j} for j in raw_jobs]}
    except Exception as e:
        print(f"❌ WWR Node Failed: {e}")
        return {"raw_results": []}

# --- 2. The Normalizer ---
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
                    
                    # --- FIX 1: Map RemoteOK Company ---
                    company=payload.get("company", "Unknown"), 
                    # -----------------------------------
                    
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
                    
                    # --- FIX 2: Map Upwork Company (If available) ---
                    # Upwork RSS rarely gives company names publicly, but we set a default
                    company="Upwork Client", 
                    # ------------------------------------------------
                    
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
                    
                    # --- FIX 3: Map WWR Company ---
                    company=payload.get("company", "Unknown"),
                    # ------------------------------
                    
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

            elif source == "google_search":
                job = Job(
                    id=payload.get("id"),
                    platform="google_search", # Could be LinkedIn/Naukri
                    title=payload.get("title"),
                    company="See URL",
                    description=payload.get("description"),
                    url=payload.get("url")
                )
                normalized_jobs.append(job)    
                
        except Exception as e:
            print(f"⚠️ Failed to normalize a {source} job: {e}")
            continue

    print(f"✅ Normalized {len(normalized_jobs)} valid jobs.")
    return {"normalized_jobs": normalized_jobs}

# --- 3. The Scorer (Use ONLY this one) ---

def score_jobs(state: JobState):
    normalized = state.get("normalized_jobs", [])
    query = state.get("search_query", "Python Developer")
    must_haves = state.get("must_have_keywords", []) # <--- Get keywords
    
    if not normalized:
        return {"filtered_jobs": []}

    # 1. APPLY HARD FILTER (Python)
    # This deletes bad jobs BEFORE the AI sees them.
    technically_qualified = strict_keyword_filter(normalized, must_haves)
    
    if not technically_qualified:
        print("⚠️ No jobs passed the hard keyword filter.")
        return {"filtered_jobs": []}

    # 2. APPLY SOFT SCORING (LLM)
    # Now the AI scores the survivors based on the Rubric
    scored = score_jobs_with_llm(technically_qualified, query)
    
    return {"filtered_jobs": scored}


# --- 4. The Drafter (NEW NODE) ---
def draft_proposals_node(state: JobState):
    # Get the high-quality jobs from the previous step
    good_jobs = state.get("filtered_jobs", [])
    
    # Take only the top 3 to save API costs/time
    top_picks = good_jobs[:3]
    
    if not top_picks:
        return {"proposals": []}
    
    # Generate drafts
    drafts_dict = generate_proposals(top_picks)
    
    # Convert dict to a list of strings for the state
    proposal_list = list(drafts_dict.values())
    
    return {"proposals": proposal_list}

# --- 5. Notifier Node (NEW) ---
def notify_user(state: JobState):
    # Get the jobs we drafted proposals for (Top picks)
    top_jobs = state.get("filtered_jobs", [])
    proposals = state.get("proposals", [])
    
    # We only notify for the absolute best (e.g. top 3 that got drafts)
    # Assuming proposals align with the top_jobs[:len(proposals)]
    
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

# --- . Logger Node (NEW) ---
def log_results_node(state: JobState):
    # Get the top jobs (filtered)
    top_jobs = state.get("filtered_jobs", [])
    
    # Get Sheet URL from state (or env var)
    sheet_url = os.getenv("GOOGLE_SHEET_URL") # We will set this in .env
    
    if top_jobs and sheet_url:
        log_jobs_to_sheet(top_jobs, sheet_url)
        
    return {}

def tailor_node(state: JobState):
    top_jobs = state.get("filtered_jobs", [])
    
    # 1. Debug Profile Loading
    try:
        with open("profile.md", "r", encoding="utf-8") as f:
            base_resume = f.read()
        print("✅ Found 'profile.md', loaded successfully.")
    except FileNotFoundError:
        print("❌ ERROR: 'profile.md' not found in root directory!")
        return {}
    except Exception as e:
        print(f"❌ ERROR reading profile: {e}")
        return {}

    tailored_paths = []
    
    print(f"👔 Checking {len(top_jobs)} jobs for tailoring candidates (Score >= 85)...")
    
    count = 0
    for job in top_jobs:
        # Debugging: Print the score of the top candidates
        if count < 5: 
            print(f"   - Checking: {job.title} (Score: {job.relevance_score})")
        
        if job.relevance_score >= 85:
            print(f"   ✨ Generating resume for: {job.title}...")
            
            try:
                # Generate
                new_resume = tailor_resume(job, base_resume)
                
                # Save
                path = save_tailored_resume(new_resume, job.company, job.title)
                tailored_paths.append(path)
                print(f"      📂 Saved to: {path}")
                
            except Exception as e:
                print(f"      ❌ Failed to generate/save: {e}")
        else:
            # Stop printing after a few low scores to keep logs clean
            pass
            
        count += 1

    if not tailored_paths:
        print("⚠️ No resumes generated. (Did any job score >= 85?)")

    return {"tailored_resumes": tailored_paths}

# --- 6. Graph Construction ---

def create_graph():
    workflow = StateGraph(JobState)

    workflow.add_node("remoteok_fetcher", fetch_remoteok)
    workflow.add_node("wwr_fetcher", fetch_wwr)
    workflow.add_node("upwork_fetcher", fetch_upwork)
    workflow.add_node("normalizer", normalize_data)
    workflow.add_node("scorer", score_jobs)
    workflow.add_node("drafter", draft_proposals_node)
    workflow.add_node("notifier", notify_user)
    workflow.add_node("logger", log_results_node)
    workflow.add_node("tailor", tailor_node)
    workflow.add_node("freelancer_fetcher", fetch_freelancer_api)
    workflow.add_node("google_fetcher", fetch_google_jobs)

    workflow.set_entry_point("remoteok_fetcher") 
    workflow.add_edge("remoteok_fetcher", "wwr_fetcher")
    workflow.add_edge("wwr_fetcher", "upwork_fetcher")   
    # workflow.add_edge("upwork_fetcher", "normalizer")
    workflow.add_edge("upwork_fetcher", "freelancer_fetcher")
    workflow.add_edge("freelancer_fetcher", "google_fetcher")
    workflow.add_edge("google_fetcher", "normalizer")
    workflow.add_edge("normalizer", "scorer")
    workflow.add_edge("scorer", "tailor")  
    workflow.add_edge("tailor", "drafter")
    workflow.add_edge("drafter", "notifier")
    workflow.add_edge("notifier", "logger")
    workflow.add_edge("logger", END)      

    return workflow.compile()
