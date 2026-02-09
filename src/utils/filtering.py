from typing import List
from ..models.job import Job

def strict_keyword_filter(jobs: List[Job], must_haves: List[str]) -> List[Job]:
    """
    Filters jobs based on must-have keywords.
    EXCEPTION: Google Search results are skipped (trusted) because they only have snippets.
    """
    if not must_haves:
        return jobs

    print(f"🕵️ Applying Hard Filter: Must contain {must_haves}")
    
    filtered = []
    dropped_count = 0
    
    for job in jobs:
        # --- LOGIC START ---
        # 1. Trust Google Search & Freelancer (because descriptions are too short)
        if job.platform in ["google_search", "freelancer"]:
            filtered.append(job)
            continue
        # -------------------

        # 2. For others (RemoteOK, WWR), check full description
        text_to_check = (job.title + " " + job.description).lower()
        
        # Check if ALL keywords exist
        if all(keyword.lower() in text_to_check for keyword in must_haves):
            filtered.append(job)
        else:
            dropped_count += 1

    print(f"📉 Filter dropped {dropped_count} jobs.")
    return filtered