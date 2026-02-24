import argparse
import os
import sys
from datetime import datetime
from src.graph.workflow import create_graph
from src.utils.persistence import save_new_matches, get_already_saved_ids, log_job_hunt

# --- 1. THE 19 TARGETED ROLES ---
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

def get_role_for_current_time():
    """Calculates exactly which role to run, cycling through the entire list over multiple days."""
    now = datetime.utcnow()
    
    # 1. Get a stable day counter (days since Unix epoch)
    days_since_epoch = (now - datetime(1970, 1, 1)).days
    
    # 2. Identify which 96-minute interval we are in (0 to 14)
    minutes_since_midnight = now.hour * 60 + now.minute
    interval_index = (minutes_since_midnight // 96) % 15
    
    # 3. Use the day counter as an offset so the starting role shifts every day
    # This ensures that roles at indices 15-18 get searched regularly
    total_index = (days_since_epoch * 15 + interval_index) % len(TARGET_ROLES)
    
    return TARGET_ROLES[total_index]

def run_automation(role_name):
    """Executes the autonomous job hunt for a specific role."""
    print(f"\n🚀 STARTING JOB HUNT: {role_name}")
    
    # 1. Initialize the Graph
    app = create_graph()
    
    # 2. Set Initial State
    initial_state = {
        "search_query": role_name, # Matches the key used in your workflow
        "must_have_keywords": ["Node", "React", "Python", "TypeScript", "AI"], 
        "selected_platforms": PLATFORMS_TO_SEARCH,
        "raw_results": [],
        "normalized_jobs": [],
        "filtered_jobs": [],
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

        # 4. Log successful completion to prevent redundant runs
        log_job_hunt(role_name)
        
    except Exception as e:
        print(f"❌ Automation Error for {role_name}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HustleBot Cron Job Hunter")
    # Make --role optional so --once can work
    parser.add_argument("--role", type=str, help="Specific job title to search")
    parser.add_argument("--once", action="store_true", help="Run the assigned role for the current time interval")
    
    args = parser.parse_args()

    # Determine which role to run
    if args.role:
        target_role = args.role
    elif args.once:
        target_role = get_role_for_current_time()
    else:
        # Fallback if no flags are provided
        target_role = get_role_for_current_time()

    run_automation(target_role)