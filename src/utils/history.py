import json
import os
from typing import Set

HISTORY_FILE = "job_history.json"

def load_history() -> Set[str]:
    """Loads the set of processed Job IDs from the local JSON file."""
    if not os.path.exists(HISTORY_FILE):
        return set()
    try:
        with open(HISTORY_FILE, "r") as f:
            data = json.load(f)
            return set(data)
    except Exception:
        return set()

def save_to_history(job_id: str):
    """Adds a single Job ID to history and saves to file."""
    history = load_history()
    if job_id not in history:
        history.add(job_id)
        with open(HISTORY_FILE, "w") as f:
            json.dump(list(history), f)

def get_history_stats():
    """Returns count of tracked jobs."""
    return len(load_history())