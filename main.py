import os
import sys
from dotenv import load_dotenv  # <--- NEW IMPORT
from src.graph.workflow import create_graph

# --- 1. Load Configuration ---
def load_config():
    """
    Loads configuration from .env file.
    """
    print("⚙️ Loading configuration from .env...")
    
    # This finds the .env file in your root folder and loads it
    load_dotenv()

    # Debug: Check if critical keys are loaded
    api_key = os.getenv("GOOGLE_API_KEY")
    sheet_url = os.getenv("GOOGLE_SHEET_URL")
    tele_token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not api_key:
        print("❌ ERROR: GOOGLE_API_KEY not found in .env")
        sys.exit(1)
        
    if not sheet_url:
        print("⚠️ WARNING: GOOGLE_SHEET_URL not found. Logging to Sheets will fail.")
        
    if not tele_token:
        print("⚠️ WARNING: TELEGRAM_BOT_TOKEN not found. Alerts will be skipped.")
    
    print("✅ Configuration loaded successfully.")

# --- 2. Main Execution ---
def main():
    load_config()
    
    print("\n🚀 Starting Job Agent...")
    
    # Define your search parameters (You can also move these to .env if you want!)
    QUERY = os.getenv("SEARCH_QUERY", "Python Developer")
    MUST_HAVES = os.getenv("MUST_HAVE_KEYWORDS", "").split(",")
    # Clean up the list (remove empty strings)
    MUST_HAVES = [k.strip() for k in MUST_HAVES if k.strip()]
    
    # Get Upwork URL from .env or ignore
    upwork_url = os.getenv("UPWORK_RSS_URL")

    # Initialize Graph
    app = create_graph()
    
    initial_state = {
        "search_query": QUERY,
        "must_have_keywords": MUST_HAVES,
        "upwork_rss_url": upwork_url,
        "raw_results": [],
        "normalized_jobs": [],
        "filtered_jobs": [],
        "proposals": []
    }

    try:
        # Run the Workflow
        results = app.invoke(initial_state)
        
        print("\n✅ Execution Finished.")
        
        # Summary
        print(f"Total Jobs Processed: {len(results.get('normalized_jobs', []))}")
        print(f"Qualified Matches: {len(results.get('filtered_jobs', []))}")
        print(f"Drafts Generated: {len(results.get('proposals', []))}")

    except Exception as e:
        print(f"\n❌ Workflow Crashed: {e}")

if __name__ == "__main__":
    main()