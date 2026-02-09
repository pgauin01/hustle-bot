import streamlit as st
import pandas as pd
import os
from src.graph.workflow import create_graph
from dotenv import load_dotenv
from src.llm.query_generator import generate_search_queries
import json

# Load .env into process environment (so os.getenv works)
load_dotenv()

# Page Config
st.set_page_config(page_title="HustleBot", page_icon="💼", layout="wide")

# Custom CSS for a cleaner look
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
    .job-card { padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0; margin-bottom: 20px; }
    .score-high { color: #008000; font-weight: bold; }
    .score-med { color: #ffa500; font-weight: bold; }
    .score-low { color: #ff0000; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

def load_settings():
    if os.path.exists("user_settings.json"):
        with open("user_settings.json", "r") as f:
            return json.load(f)
    return {"upwork_url": "", "api_key": ""}

def save_settings(upwork_url, api_key):
    with open("user_settings.json", "w") as f:
        json.dump({"upwork_url": upwork_url, "api_key": api_key}, f)

def main():
    saved_config = load_settings()
    
    # --- SIDEBAR DESIGN START ---
    with st.sidebar:
        st.title("🤖 HustleBot")
        st.caption("Your AI Job Agent")
        # st.divider()

        # 1. SEARCH SECTION (Prominent)
        st.markdown("### 🎯 Job Search")
        
        # Auto-Suggest Logic
        if st.button("✨ Auto-Suggest Strategy", type="secondary", use_container_width=True):
            with st.spinner("Analyzing profile..."):
                suggestions = generate_search_queries()
                st.session_state['query_suggestions'] = suggestions
        
        if 'query_suggestions' in st.session_state:
            selected = st.pills("Suggested Strategies:", st.session_state['query_suggestions'], selection_mode="single")
            if selected:
                st.session_state['current_query'] = selected

        default_query = st.session_state.get('current_query', "python developer")
        query = st.text_input("Target Role", value=default_query)

        st.markdown("### 🛡️ Hard Filters")
        keywords_str = st.text_input(
            "Must-Have Keywords (comma separated)", 
            placeholder="e.g. Django, Remote, AWS",
            help="Jobs MISSING these words will be instantly rejected."
        )
        
        # Parse string into list
        must_haves = [k.strip() for k in keywords_str.split(",")] if keywords_str else []
        
        # Primary Action Button
        st.write("") # Spacer
        run_btn = st.button("🚀 Find Jobs", type="primary", use_container_width=True)
        
        st.divider()

        # 2. CONFIGURATION SECTION (Collapsible)
        with st.expander("⚙️ Settings & Keys", expanded=False):
            st.info("Configure your keys once and save.")
            
            # API Key
            # Upwork Link
            upwork_url_input = st.text_input("Upwork RSS Link", value=saved_config.get("upwork_url", ""))
            if upwork_url_input:
                st.caption("✅ Upwork Linked")
            else:
                st.caption("❌ Upwork Not Linked (Mock Mode)")
                
            if st.button("💾 Save Config"):
                save_settings(upwork_url_input)
                st.success("Saved!")

        # 3. PROFILE PREVIEW (Mini)
        with st.expander("👤 My Profile", expanded=False):
            # Load current profile text
            try:
                with open("profile.md", "r") as f:
                    current_profile = f.read()
            except FileNotFoundError:
                current_profile = ""

            # Show the text area for editing
            new_profile = st.text_area("Your Bio / Skills", value=current_profile, height=150)
            
            # Save Button
            if st.button("💾 Save Profile"):
                with open("profile.md", "w") as f:
                    f.write(new_profile)
                st.success("Profile Updated!")
                # Force a rerun so the new profile is immediately used
                st.rerun()

        # Footer Status
        st.divider()
        st.markdown("Sources Active:")
        st.markdown("🟢 RemoteOK")
        st.markdown("🟢 WeWorkRemotely")
        if saved_config.get("upwork_url"):
            st.markdown("🟢 Upwork (Live)")
        else:
            st.markdown("🔴 Upwork (Mock)")

    # Main Area
    st.title(f"Jobs for: *{query}*")

    if run_btn:
        # Create a container to show progress
        status_box = st.status("🚀 Agent Active...", expanded=True)
        
        try:
            # 1. Init Graph
            app = create_graph()
            
            initial_state = {
                "search_query": query,
                "upwork_rss_url": saved_config.get("upwork_url", ""),
                "raw_results": [],
                "normalized_jobs": [],
                "filtered_jobs": [],
                "proposals": [],
                "must_have_keywords": must_haves,
            }

            # 2. Run Workflow with Streaming
            # We use a dictionary to accumulate the final results as they come in
            final_state = {} 
            
            for event in app.stream(initial_state):
                # 'event' is a dict like: {'remoteok_fetcher': {'raw_results': [...]}}
                for node_name, output in event.items():
                    
                    # Update our local state copy
                    final_state.update(output)
                    
                    # --- DYNAMIC UI UPDATES ---
                    if node_name == "remoteok_fetcher":
                        count = len(output.get('raw_results', []))
                        status_box.write(f"✅ RemoteOK found {count} jobs.")
                        
                    elif node_name == "wwr_fetcher":
                        count = len(output.get('raw_results', []))
                        status_box.write(f"✅ WeWorkRemotely found {count} jobs.")
                        
                    elif node_name == "upwork_fetcher":
                        count = len(output.get('raw_results', []))
                        status_box.write(f"✅ Upwork found {count} jobs.")
                        
                    elif node_name == "normalizer":
                        count = len(output.get('normalized_jobs', []))
                        status_box.write(f"🔄 Cleaned & Normalized {count} jobs.")
                        
                    elif node_name == "scorer":
                        # The scorer outputs 'filtered_jobs' (the ones that passed)
                        # But we might want to know how many were scored total
                        scored_count = len(output.get('filtered_jobs', []))
                        status_box.write(f"🧠 AI Scored & Filtered jobs. (Top {scored_count} retained)")
                        
                    elif node_name == "drafter":
                        draft_count = len(output.get('proposals', []))
                        status_box.write(f"✍️ Generated {draft_count} Draft Proposals.")

            # 3. Finalize
            status_box.update(label="✅ Workflow Complete!", state="complete", expanded=False)
            
            # Store results in session state
            st.session_state['results'] = final_state
            st.success("Analysis Complete!")
            
        except Exception as e:
            status_box.update(label="❌ Workflow Failed", state="error")
            st.error(f"Error: {e}")

    # Display Results if they exist
    if 'results' in st.session_state:
        result = st.session_state['results']
        all_jobs = result.get("normalized_jobs", [])
        top_jobs = result.get("filtered_jobs", [])
        proposals = result.get("proposals", [])

        # Metrics Row
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Jobs Found", len(all_jobs))
        col2.metric("Qualified Matches (>70%)", len(top_jobs))
        col3.metric("Drafts Generated", len(proposals))

        # Tabs
        tab1, tab2 = st.tabs(["🏆 Top Picks & Proposals", "📊 All Jobs Data"])

        with tab1:
            if not top_jobs:
                st.warning("No jobs met the quality threshold.")
            else:
                # Top Picks Loop
                for i, job in enumerate(top_jobs[:5]): # Show top 5
                    with st.container():
                        # Determine score color
                        score = job.relevance_score
                        color = "green" if score > 80 else "orange"
                        
                        # Layout
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            st.subheader(f"{i+1}. {job.title}")
                            st.caption(f"📍 {getattr(job, 'company', 'Unknown')} | 🔗 [View Job]({job.url})")
                            st.write(f"**Why:** {job.reasoning}")
                        with c2:
                            st.markdown(f"## :{color}[{score}/100]")
                        
                        # Proposal Draft (if available for this job)
                        # We assume proposals align with the top jobs list
                        if i < len(proposals):
                            with st.expander("📝 View AI Draft Proposal"):
                                st.text_area("Copy this:", value=proposals[i], height=300)
                        
                        st.divider()

        with tab2:
            # Data Table view
            data = []
            for j in all_jobs:
                data.append({
                    "Score": j.relevance_score,
                    "Title": j.title,
                    "Platform": j.platform,
                    "Budget/Salary": f"{j.budget_min} - {j.budget_max}" if j.budget_max > 0 else "Not listed",
                    "URL": j.url
                })
            df = pd.DataFrame(data)
            # Sort by score
            df = df.sort_values(by="Score", ascending=False)
            st.dataframe(df, use_container_width=True)

if __name__ == "__main__":
    main()

