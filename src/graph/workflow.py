from langgraph.graph import StateGraph, END
from .state import JobState
from ..models.job import Job
from ..utils.cleaning import clean_html
from ..platforms.remoteok import fetch_from_remoteok
from ..llm.scoring import score_jobs_with_llm

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
    
def score_jobs(state: JobState):
    normalized = state.get("normalized_jobs", [])
    query = state.get("search_query", "Python Developer")
    
    if not normalized:
        return {"filtered_jobs": []}

    # Run the LLM
    scored = score_jobs_with_llm(normalized, query)
    
    # Filter: Keep only jobs with Score > 50 (or keep all to see results)
    # Let's keep all for now so you can see the AI working
    return {"filtered_jobs": scored}    



def fetch_upwork(state: JobState):
    # Mock for now, pending RSS implementation
    print("🌍 Fetching Upwork (Mock)...")
    mock_job = {
        "id": "123", 
        "title": "Backend Dev", 
        "description": "<p>Need a fast api expert</p>",
        "budget": 500
    }
    return {"raw_results": [{"source": "upwork", "payload": mock_job}]}

# --- 2. The Normalizer (Context Switcher) ---

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
                    posted_at=payload.get("date") # Needs parsing in V2
                )
                normalized_jobs.append(job)

            elif source == "upwork":
                # Handle our mock (or future RSS) data
                job = Job(
                    id=payload.get("id"),
                    platform="upwork",
                    title=payload.get("title"),
                    description=clean_html(payload.get("description")),
                    url=f"https://upwork.com/jobs/{payload.get('id')}",
                    budget_min=float(payload.get("budget", 0)),
                    budget_max=float(payload.get("budget", 0)),
                    skills=[], # RSS usually provides this, mock might not
                )
                normalized_jobs.append(job)
                
        except Exception as e:
            print(f"⚠️ Failed to normalize a {source} job: {e}")
            continue

    print(f"✅ Normalized {len(normalized_jobs)} valid jobs.")
    return {"normalized_jobs": normalized_jobs}

# --- 3. Scorer Placeholder ---

def score_jobs(state: JobState):
    # Just pass through for now
    return {"filtered_jobs": state["normalized_jobs"]}

# --- 4. Graph Construction ---

def create_graph():
    workflow = StateGraph(JobState)

    # 1. Add Nodes
    workflow.add_node("remoteok_fetcher", fetch_remoteok)
    workflow.add_node("upwork_fetcher", fetch_upwork)
    workflow.add_node("normalizer", normalize_data)
    workflow.add_node("scorer", score_jobs)

    # 2. Define the Flow
    # START -> RemoteOK -> Upwork -> Normalizer -> Scorer -> END
    
    # ⚠️ CRITICAL CHANGE: Start with remoteok, not upwork
    workflow.set_entry_point("remoteok_fetcher") 
    
    workflow.add_edge("remoteok_fetcher", "upwork_fetcher")
    workflow.add_edge("upwork_fetcher", "normalizer")
    workflow.add_edge("normalizer", "scorer")
    workflow.add_edge("scorer", END)

    return workflow.compile()