from typing import List
from ..models.job import Job

def strict_keyword_filter(jobs: List[Job], must_haves: List[str]) -> List[Job]:
    """
    Returns only jobs that contain ALL mandatory keywords.
    Case-insensitive.
    """
    if not must_haves:
        return jobs

    print(f"🕵️ Applying Hard Filter: Must contain {must_haves}")
    passed_jobs = []

    for job in jobs:
        # Combine title and description for search
        content = (job.title + " " + job.description).lower()
        
        # Check if ALL keywords exist in the content
        # Use simple string matching (fast & strict)
        if all(keyword.lower() in content for keyword in must_haves):
            passed_jobs.append(job)
        else:
            # Optional: Log why it failed (e.g., "Missing 'Django'")
            pass

    print(f"📉 Filter dropped {len(jobs) - len(passed_jobs)} jobs.")
    return passed_jobs