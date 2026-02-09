import os
import asyncio
from src.graph.workflow import create_graph

# Load config from Environment Variables (set by GitHub Actions)
QUERY = os.getenv("SEARCH_QUERY", "Python Developer")
MUST_HAVES = os.getenv("MUST_HAVE_KEYWORDS", "").split(",")
MUST_HAVES = [k.strip() for k in MUST_HAVES if k.strip()]

def run_bot():
    print(f"🚀 Starting Headless Agent...")
    print(f"🎯 Query: {QUERY}")
    print(f"🛡️ Filters: {MUST_HAVES}")

    # 1. Init Graph
    app = create_graph()
    
    # 2. Define State
    initial_state = {
        "search_query": QUERY,
        "must_have_keywords": MUST_HAVES,
        "upwork_rss_url": None, # Hard to maintain RSS cookies in cloud, skipping Upwork for auto-runs
        "raw_results": [],
        "normalized_jobs": [],
        "filtered_jobs": [],
        "proposals": []
    }

    # 3. Run
    # We use invoke() because we don't need streaming updates in the cloud logs
    results = app.invoke(initial_state)
    
    # 4. Report
    draft_count = len(results.get("proposals", []))
    print(f"✅ Run Complete. Generated {draft_count} proposals.")

if __name__ == "__main__":
    run_bot()