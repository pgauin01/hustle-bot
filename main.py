from src.graph.workflow import create_graph

def main():
    print("🚀 Starting Job Agent...")
    
    # 1. Initialize the Graph
    app = create_graph()
    
    # 2. Define the initial state (what we are looking for)
    initial_state = {
        "search_query": "python developer",
        "raw_results": [],       # Start empty
        "normalized_jobs": [],   # Start empty
        "filtered_jobs": [],     # Start empty
        "proposals": []          # Start empty
    }
    
    # 3. Run the workflow
    # This will trigger fetch_remoteok (real) and others (mock) in parallel
    result = app.invoke(initial_state)
    
    # 4. Print the results
    raw_count = len(result["raw_results"])
    print(f"\n✅ Execution Finished.")
    print(f"Total Raw Jobs Collected: {raw_count}")
    
    # Show sources breakdown
    sources = {}
    for item in result["raw_results"]:
        src = item["source"]
        sources[src] = sources.get(src, 0) + 1
    print(f"Breakdown by Source: {sources}")

    # Show a sample from RemoteOK (Real Data)
    remote_ok_samples = [x for x in result["raw_results"] if x["source"] == "remoteok"]
    if remote_ok_samples:
        sample = remote_ok_samples[0]["payload"]
        print(f"\n🔎 Sample Real Job (RemoteOK):")
        print(f"Title: {sample.get('position')}")
        print(f"Company: {sample.get('company')}")
        print(f"URL: {sample.get('url')}")

if __name__ == "__main__":
    main()