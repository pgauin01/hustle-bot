import requests
from ..graph.state import JobState

def fetch_freelancer_api(state: JobState):
    query = state.get("search_query", "python")
    print(f"🦅 Fetching Freelancer.com for '{query}'...")
    
    url = "https://www.freelancer.com/api/projects/0.1/projects/active"
    params = {
        "query": query,
        "limit": 20,
        "sort_field": "time_updated",
        "job_details": "true" # Get description
    }
    
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        
        projects = data.get("result", {}).get("projects", [])
        
        results = []
        for p in projects:
            results.append({
                "source": "freelancer",
                "payload": {
                    "id": p.get("id"),
                    "title": p.get("title"),
                    "description": p.get("preview_description"),
                    "url": f"https://www.freelancer.com/projects/{p.get('seo_url')}",
                    "budget_min": p.get("budget", {}).get("minimum"),
                    "budget_max": p.get("budget", {}).get("maximum"),
                    "currency": p.get("currency", {}).get("code")
                }
            })
            
        return {"raw_results": results}
        
    except Exception as e:
        print(f"❌ Freelancer API Failed: {e}")
        return {"raw_results": []}