import argparse
import os
import sys
from datetime import datetime
from src.graph.workflow import create_graph
from src.utils.persistence import save_new_matches, get_already_saved_ids, log_job_hunt

# --- 1. THE 15 TARGETED ROLES ---
TARGET_ROLES = [
    "Senior Full Stack Engineer", "AI Application Engineer", "LLM Engineer",
    "Generative AI Engineer", "RAG Engineer", "AI Product Engineer",
    "AI Systems Engineer", "Founding Engineer (AI)", "Full Stack AI Engineer",
    "Machine Learning Engineer", "Backend Engineer (AI)", "Principal AI Engineer",
    "Staff Software Engineer", "React Native AI Engineer", "Python AI Engineer", 
    "Smart Contract Engineer" , "Solidity Developer", "Ethereum Developer",
    "Blockchain Developer" 
]

PLATFORMS_TO_SEARCH = ["RemoteOK", "WeWorkRemotely", "Freelancer", "LinkedIn"]

def run_automation(role_name):
    """Executes the autonomous job hunt for a specific role."""
    print(f"\n🚀 CRON TRIGGERED: {role_name}")
    
    # 1. Initialize the Graph
    app = create_graph()
    
    # 2. Set Initial State
    # seen_job_ids ensures we don't re-process jobs across different role runs
    initial_state = {
        "role": role_name,
        "raw_results": [],
        "normalized_jobs": [],
        "filtered_jobs": [],
        "must_have_keywords": ["Node", "React", "Python", "TypeScript", "AI"], 
        "seen_job_ids": get_already_saved_ids()
    }

    # 3. Run Workflow
    try:
        final_state = app.invoke(initial_state)
        found_jobs = final_state.get("filtered_jobs", [])

        if found_jobs:
            print(f"✨ Found {len(found_jobs)} elite matches for '{role_name}'. Sending to persistence...")
            # Persistence handles the 15-job daily cap
            save_new_matches(found_jobs)
        else:
            print(f"✅ Run finished: No new elite matches for '{role_name}' at this time.")

        # 4. Log successful completion
        log_job_hunt(role_name)
        
    except Exception as e:
        print(f"❌ Automation Error for {role_name}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HustleBot Cron Job Hunter")
    parser.add_argument("--role", type=str, required=True, help="Job title passed by GitHub Actions")
    
    args = parser.parse_args()
    run_automation(args.role)