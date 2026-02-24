import os
import sys
from datetime import datetime
from src.graph.workflow import create_graph

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

def get_role_for_current_time():
    """Calculates exactly which role to run based on the current UTC time."""
    now = datetime.utcnow()
    minutes_since_midnight = now.hour * 60 + now.minute
    
    # Divide the day into 96-minute chunks to get an index from 0 to 14
    index = (minutes_since_midnight // 96) % len(TARGET_ROLES)
    return TARGET_ROLES[index]

def job_hunt_task(forced_role=None):
    # Import persistence tools here to ensure the environment is loaded first
    from src.utils.persistence import get_already_saved_ids, log_job_hunt, should_skip_run
    
    # 1. Determine the role to search
    role = forced_role if forced_role else get_role_for_current_time()
    
    if forced_role:
        print(f"\n🧪 LOCAL TEST MODE: Forcing hunt for {role}")
    else:
        print(f"\n⏰ Waking up for scheduled interval! Assigned Role: {role}")
        
        # --- THE FIX: Check the Cooldown Brain ---
        # If it's an automated run, check if we already searched this recently
        if should_skip_run(role, hours_cooldown=12):
            print(f"⏩ SKIPPING: '{role}' was already searched in the last 12 hours.")
            print("💰 Saved unnecessary API calls. Going back to sleep.")
            return  # Exits the script immediately!
    
    # 2. Get historical IDs to prevent scoring duplicates
    global_seen_ids = get_already_saved_ids()
    print(f"📚 Loaded {len(global_seen_ids)} existing jobs to prevent duplicates.")

    # 3. Initialize the LangGraph Workflow
    app = create_graph()
    
    initial_state = {
        "search_query": role,
        "must_have_keywords": [],
        "selected_platforms": PLATFORMS_TO_SEARCH,
        "raw_results": [], 
        "normalized_jobs": [], 
        "filtered_jobs": [],
        "seen_job_ids": global_seen_ids 
    }
    
    # 4. Run the Pipeline
    try:
        results = app.invoke(initial_state)
        found_jobs = results.get("filtered_jobs", [])
        print(f"✅ Finished. Saved {len(found_jobs)} Top Matches for {role}.")
        
        # --- UPDATE THE BRAIN ---
        # Log this successful run so it doesn't trigger again for 12 hours
        log_job_hunt(role)
        
    except Exception as e:
        print(f"❌ Error during '{role}': {e}")


# --- CLI LISTENER FOR TESTING ---
if __name__ == "__main__":
    
    # If you type: python automate.py --role "RAG Engineer"
    if len(sys.argv) == 3 and sys.argv[1] == "--role":
        target = sys.argv[2]
        job_hunt_task(forced_role=target)
        
    # If the GitHub Action types: python automate.py --once
    elif len(sys.argv) == 2 and sys.argv[1] == "--once":
        job_hunt_task()
        
    # Standard fallback
    else:
        job_hunt_task()