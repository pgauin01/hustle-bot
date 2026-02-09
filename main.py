from dotenv import load_dotenv
from src.graph.workflow import create_graph

def main():
    load_dotenv()
    print("Starting Job Agent...")
    
    # 1. Initialize the Graph
    app = create_graph()
    
    # 2. Define the initial state 
    # TIP: Use single-word tags for RemoteOK (e.g., "python", "react", "backend")
    initial_state = {
        "search_query": "python", 
        "raw_results": [],       
        "normalized_jobs": [],   
        "filtered_jobs": [],     
        "proposals": []          
    }
    
    # 3. Run the workflow
    result = app.invoke(initial_state)
    
    # 4. Print the results
    raw_count = len(result["raw_results"])
    print(f"Execution Finished.")
    print(f"Total Raw Jobs Collected: {raw_count}")
    
    # Show sources breakdown
    sources = {}
    for item in result["raw_results"]:
        src = item["source"]
        sources[src] = sources.get(src, 0) + 1
    print(f"Breakdown by Source: {sources}")
    
    # Show AI Scores (Top 3)
    scored = result.get("filtered_jobs", [])
    if scored:
        print(f"\n✅ Top 3 AI Recommendations:")
        for job in scored[:3]:
            print(f"- [Score: {job.relevance_score}] {job.title} ({job.platform})")
            print(f"  Reason: {job.reasoning}")

    proposals = result.get("proposals", [])
    if proposals:
        print(f"\n✍️  Generated {len(proposals)} Draft Proposals:")
        print("="*60)
        for i, draft in enumerate(proposals):
            print(f"\n--- Proposal {i+1} ---")
            print(draft.strip())
            print("="*60)        

if __name__ == "__main__":
    main()
