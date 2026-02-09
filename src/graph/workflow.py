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
                    description=clean_html(payload.get("description", "")),
                    url=payload.get("link", ""),
                    budget_min=0.0, # WWR rarely lists salary in metadata
                    budget_max=0.0,
                    skills=[], 
                    posted_at=payload.get("published")
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

    workflow.set_entry_point("remoteok_fetcher") 
    workflow.add_edge("remoteok_fetcher", "wwr_fetcher") # <--- NEW EDGE
    workflow.add_edge("wwr_fetcher", "upwork_fetcher")   # <--- CONNECT WWR
    workflow.add_edge("upwork_fetcher", "normalizer")
    workflow.add_edge("normalizer", "scorer")
    workflow.add_edge("scorer", "drafter") # <--- Connect Scorer to Drafter
    workflow.add_edge("drafter", "notifier")
    workflow.add_edge("drafter", END)      # <--- Drafter ends the flow

    return workflow.compile()
