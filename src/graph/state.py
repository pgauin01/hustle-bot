# src/graph/state.py
from typing import List, Dict, Any, TypedDict, Annotated
import operator
from ..models.job import Job

class JobState(TypedDict):
    # INPUT: What the user is looking for
    search_query: str 
    must_have_keywords: List[str]
    
    # STEP 1: Raw data collection (Append-only to allow parallel writes)
    # Each fetcher adds to this list: {"source": "upwork", "payload": {...}}
    raw_results: Annotated[List[Dict[str, Any]], operator.add]
    
    # STEP 2: Normalized Data
    normalized_jobs: List[Job]
    
    # STEP 3: Intelligence & Output
    filtered_jobs: List[Job]   # Jobs that passed the AI check
    proposals: List[str]       # Drafted cover letters for top jobs
    google_search_sites: List[str]