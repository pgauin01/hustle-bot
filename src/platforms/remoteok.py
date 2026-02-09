import logging
import requests
from typing import List, Dict, Any

from ..graph.state import JobState

# RemoteOK requires a User-Agent to avoid 429/403 errors
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def fetch_from_remoteok(tag: str = "python") -> List[Dict[str, Any]]:
    """
    Fetches jobs from RemoteOK API.
    API behavior: Returns a list where [0] is legal info, [1..n] are jobs.
    """
    url = "https://remoteok.com/api"
    
    # RemoteOK works best with single-word tags (e.g., "python", "engineer", "exec").
    # If the user sends "python developer", we take the first word "python" to ensure results.
    clean_tag = tag.split(" ")[0].lower() if tag else "python"
    
    params = {"tag": clean_tag}
    
    print(f"📡 Connecting to RemoteOK API (tag='{clean_tag}')...")
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Filter out the "legal" metadata and ensure items are dictionaries
        jobs = [
            item for item in data 
            if isinstance(item, dict) and "legal" not in item
        ]
        
        # NOTE: RemoteOK provides a "location" field (e.g., "Worldwide", "North America Only")
        return jobs
    
    except Exception as e:
        print(f"❌ RemoteOK Error: {e}")
        return []

def fetch_remoteok(state: JobState):
    query = state.get("search_query", "python")
    
    # 1. Execute the fetch
    raw_jobs = fetch_from_remoteok(tag=query)
    
    # 2. Structure the data for the 'raw_results' list in state
    results_wrapper = [
        {"source": "remoteok", "payload": job} 
        for job in raw_jobs
    ]
    
    return {"raw_results": results_wrapper}