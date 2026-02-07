import logging
from typing import List, Dict, Any, Optional

import requests

from ..graph.state import JobState

# RemoteOK requires a User-Agent to avoid 429/403 errors
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

REMOTEOK_API_URL = "https://remoteok.com/api"
LOGGER = logging.getLogger(__name__)

def fetch_from_remoteok(tag: Optional[str] = None) -> List[Dict[str, Any]]:
    params: Dict[str, str] = {}
    if tag:
        params["tag"] = tag

    try:
        response = requests.get(
            REMOTEOK_API_URL,
            headers=HEADERS,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        LOGGER.warning("RemoteOK request failed: %s", exc)
        return []
    except ValueError as exc:
        LOGGER.warning("RemoteOK returned invalid JSON: %s", exc)
        return []

    if not isinstance(payload, list):
        LOGGER.warning("RemoteOK payload unexpected type: %s", type(payload).__name__)
        return []

    jobs = [
        item for item in payload
        if isinstance(item, dict) and item.get("position")
    ]

    if tag:
        tag_lower = tag.lower()
        jobs = [
            job for job in jobs
            if any(tag_lower == t.lower() for t in job.get("tags", []))
        ]

    return jobs

def fetch_remoteok(state: JobState):
    query = state.get("search_query", "python")
    
    # 1. Execute the fetch
    raw_jobs = fetch_from_remoteok(tag=query)
    
    # 2. Structure the data for the 'raw_results' list in state
    # We wrap it in a dict to identify the source later in the Normalizer
    results_wrapper = [
        {"source": "remoteok", "payload": job} 
        for job in raw_jobs
    ]
    
    return {"raw_results": results_wrapper}

if __name__ == "__main__":
    # Quick test if you run this file directly
    results = fetch_from_remoteok("python")
    print(f"First job title: {results[0].get('position') if results else 'None'}")
