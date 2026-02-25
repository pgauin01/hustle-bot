import os
import sys
from datetime import datetime

# Import your models and persistence functions
from src.models.job import Job
from src.utils.persistence import save_new_matches

def run_test():
    print("🧪 Generating 35 dummy jobs to test the 30-job limit...")
    
    dummy_jobs = []
    # Create 35 fake jobs to see if the system stops at 30
    for i in range(1, 36):
        job = Job(
            id=f"test_job_{i}",
            platform="TestBoard",
            title=f"Dummy AI Engineer {i}",
            company=f"Test Corp {i}",
            description="Just a test description.",
            url=f"https://example.com/job/{i}",
            budget_min=0,
            budget_max=0,
            is_remote=True
        )
        # Manually assign the properties the LLM usually adds
        job.relevance_score = 99
        job.posted_at = "2/24/2026" 
        job.reasoning = "Testing the persistence limits."
        
        dummy_jobs.append(job)

    print(f"📦 Created {len(dummy_jobs)} dummy jobs. Sending to Google Sheets...")
    
    # Trigger the function we want to test
    save_new_matches(dummy_jobs)
    
    print("\n✅ Test script finished!")

if __name__ == "__main__":
    run_test()