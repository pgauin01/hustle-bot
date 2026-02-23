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
    "Staff Software Engineer", "React Native AI Engineer", "Python AI Engineer"
]

PLATFORMS_TO_SEARCH = ["RemoteOK", "WeWorkRemotely", "Freelancer", "LinkedIn"]

def get_already_saved_ids():
    """Reads Google Sheets to find jobs we already saved previously."""
    try:
        from src.utils.persistence import get_sheet_connection
        sh = get_sheet_connection()
        if not sh: return []
        ws = sh.worksheet("New_Matches")
        return ws.col_values(1)[1:] # Column 1 has IDs, skip header
    except:
        return []

def get_role_for_current_time():
    """Calculates exactly which role to run based on the current UTC time."""
    now = datetime.utcnow()
    minutes_since_midnight = now.hour * 60 + now.minute
    
    # Divide the day into 96-minute chunks to get an index from 0 to 14
    index = (minutes_since_midnight // 96) % len(TARGET_ROLES)
    return TARGET_ROLES[index]

def job_hunt_task(forced_role=None):
    from src.utils.persistence import get_already_saved_ids, log_job_hunt, should_skip_run
    
    # Use the forced role if provided, otherwise calculate the time-based role
    role = forced_role if forced_role else get_role_for_current_time()
    
    if forced_role:
        print(f"\n🧪 LOCAL TEST MODE: Forcing hunt for {role}")
    else:
        print(f"\n⏰ Waking up for scheduled interval! Assigned Role: {role}")
        
        # --- THE FIX: Check the Cooldown Brain ---
        # (We only check this if it's an automated run, not a manual test)
        if should_skip_run(role, hours_cooldown=12):
            print(f"⏩ SKIPPING: '{role}' was already searched in the last 12 hours.")
            print("💰 Saved unnecessary API calls. Going back to sleep.")
            return
    
    # 2. Get historical IDs to prevent duplicates
    global_seen_ids = get_already_saved_ids()
    print(f"📚 Loaded {len(global_seen_ids)} existing jobs to prevent duplicates.")

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
    
    try:
        results = app.invoke(initial_state)
        found_jobs = results.get("filtered_jobs", [])
        print(f"✅ Finished. Saved {len(found_jobs)} Top Matches for {role}.")
        
        # --- UPDATE THE BRAIN ---
        # Log this successful automated run so it doesn't run again soon
        log_job_hunt(role)
        
    except Exception as e:
        print(f"❌ Error during '{role}': {e}")

# 3. Add the command-line listener
if __name__ == "__main__":
    import sys
    
    # If you type: python automate.py --role "RAG Engineer"
    if len(sys.argv) == 3 and sys.argv[1] == "--role":
        target = sys.argv[2]
        job_hunt_task(forced_role=target)
        
    # If you just type: python automate.py
    else:
        job_hunt_task()