import streamlit as st
import os
import json
import pandas as pd
from datetime import datetime

# Import your "Brain" - The Graph
from src.graph.workflow import create_graph

# Try importing Gemini for the suggestion feature
try:
    from google import genai
except ImportError:
    genai = None

# Page Config
st.set_page_config(page_title="HustleBot 2.1", page_icon="💼", layout="wide")

# --- HELPER: ROLE SUGGESTER ---
def suggest_roles(api_key, skills):
    """
    Uses Gemini to brainstorm job titles based on skills.
    """
    if not api_key:
        st.warning("⚠️ Please enter your Google API Key in the sidebar first!")
        return []
    
    if not genai:
        st.error("❌ google-genai library not found. Run: pip install google-genai")
        return []

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        Act as a Tech Recruiter.
        Based on these skills: "{skills}"
        Suggest 5 concise, standard job titles that I should search for on job boards.
        Return ONLY a comma-separated list of titles. 
        Example Output: Python Developer, Backend Engineer, AI Engineer
        """
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        
        # Clean up text
        text = response.text.strip()
        return [t.strip() for t in text.split(",") if t.strip()]
        
    except Exception as e:
        st.error(f"AI Error: {e}")
        return []

# --- SIDEBAR: SETTINGS ---
with st.sidebar:
    st.header("⚙️ Agent Settings")
    
    with st.expander("🔑 API Keys & Config", expanded=True):
        # Load existing settings
        if os.path.exists("user_settings.json"):
            with open("user_settings.json", "r") as f:
                settings = json.load(f)
        else:
            settings = {}

        # Input Fields
        api_key = st.text_input("Google API Key", value=settings.get("api_key", ""), type="password")
        sheet_url = st.text_input("Google Sheet URL", value=settings.get("sheet_url", ""), placeholder="https://docs.google.com/...")
        tele_token = st.text_input("Telegram Bot Token", value=settings.get("tele_token", ""), type="password")
        tele_chat = st.text_input("Telegram Chat ID", value=settings.get("tele_chat", ""))
        
        # Save Button
        if st.button("💾 Save Settings"):
            new_settings = {
                "api_key": api_key,
                "sheet_url": sheet_url,
                "tele_token": tele_token,
                "tele_chat": tele_chat
            }
            with open("user_settings.json", "w") as f:
                json.dump(new_settings, f)
            st.success("Saved!")
            st.rerun()

    # Apply Keys to Environment for this session
    if api_key: os.environ["GOOGLE_API_KEY"] = api_key
    if sheet_url: os.environ["GOOGLE_SHEET_URL"] = sheet_url
    if tele_token: os.environ["TELEGRAM_BOT_TOKEN"] = tele_token
    if tele_chat: os.environ["TELEGRAM_CHAT_ID"] = tele_chat

# --- MAIN PAGE ---
st.title("🤖 HustleBot: Autonomous Recruiter")
st.markdown("Your AI agent that finds, filters, logs, and applies to jobs for you.")

# Tabs for different views
tab_run, tab_jobs, tab_resumes, tab_proposals = st.tabs(["🚀 Run Agent", "📊 Job Matches", "📝 Tailored Resumes", "✍️ Cover Letters"])

# --- TAB 1: RUN AGENT ---
with tab_run:
    col1, col2 = st.columns([1, 2])
    
    # --- INPUT COLUMN ---
    with col1:
        st.subheader("🎯 Target")
        
        # Initialize session state for role if not exists
        if "suggested_role" not in st.session_state:
            st.session_state["suggested_role"] = "Python Developer"

        # The Inputs
        query = st.text_input("Job Role", value=st.session_state["suggested_role"])
        keywords = st.text_input("Must-Have Skills", value="Python, Django")
        
        # --- NEW: AUTO-SUGGEST FEATURE ---
        with st.expander("✨ Need help with the role?"):
            if st.button("Brainstorm Roles based on Skills"):
                if not keywords:
                    st.warning("Enter some skills above first!")
                else:
                    with st.spinner("Thinking..."):
                        suggestions = suggest_roles(api_key, keywords)
                        st.session_state["role_suggestions"] = suggestions
            
            # Display Suggestions as clickable buttons
            if "role_suggestions" in st.session_state and st.session_state["role_suggestions"]:
                st.caption("Click to apply:")
                for role in st.session_state["role_suggestions"]:
                    if st.button(f"📍 {role}", use_container_width=True):
                        st.session_state["suggested_role"] = role
                        st.rerun()
        # ---------------------------------

        st.markdown("---")
        run_btn = st.button("🚀 Start Job Hunt", type="primary", use_container_width=True)

    # --- STATUS COLUMN ---
    with col2:
        if run_btn:
            st.subheader("⚙️ Execution Log")
            status_container = st.container()
            with status_container:
                st.info("Starting Workflow...")
                
                # 1. Setup Inputs
                must_haves = [k.strip() for k in keywords.split(",") if k.strip()]
                initial_state = {
                    "search_query": query,
                    "must_have_keywords": must_haves,
                    "raw_results": [],
                    "normalized_jobs": [],
                    "filtered_jobs": [],
                    "proposals": []
                }

                # 2. Run the Graph (The Brain)
                try:
                    app = create_graph()
                    final_state = app.invoke(initial_state)
                    
                    # 3. Store results
                    st.session_state["results"] = final_state
                    st.success("✅ Workflow Complete!")
                    
                except Exception as e:
                    st.error(f"❌ Workflow Failed: {e}")

# --- TAB 2: JOB MATCHES ---
with tab_jobs:
    if "results" in st.session_state:
        results = st.session_state["results"]
        jobs = results.get("filtered_jobs", [])
        
        if not jobs:
            st.warning("No jobs found matching your criteria.")
        else:
            st.metric("Qualified Matches", len(jobs))
            
            data = []
            for j in jobs:
                comp = getattr(j, 'company', 'Unknown')
                data.append({
                    "Score": j.relevance_score,
                    "Role": j.title,
                    "Company": comp,
                    "Why": j.reasoning,
                    "Link": j.url
                })
            
            df = pd.DataFrame(data)
            
            st.dataframe(
                df, 
                column_config={
                    "Link": st.column_config.LinkColumn("Apply Url"),
                    "Score": st.column_config.ProgressColumn("Relevance", min_value=0, max_value=100)
                },
                hide_index=True,
                use_container_width=True
            )
    else:
        st.info("Run the agent to see results.")

# --- TAB 3: TAILORED RESUMES ---
with tab_resumes:
    st.subheader("📂 Generated Resumes")
    folder_path = "generated_resumes"
    
    if not os.path.exists(folder_path):
        st.warning("No 'generated_resumes' folder found. Run the agent to generate some!")
    else:
        files = [f for f in os.listdir(folder_path) if f.endswith(".md")]
        
        if not files:
            st.info("No resumes generated yet. (Did any job score > 85?)")
        else:
            for filename in files:
                file_path = os.path.join(folder_path, filename)
                
                with st.expander(f"📄 {filename}", expanded=False):
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        st.markdown("### Preview")
                        st.code(content[:500] + "...", language="markdown") 
                        
                        st.download_button(
                            label="⬇️ Download Markdown",
                            data=content,
                            file_name=filename,
                            mime="text/markdown"
                        )
                    except Exception as e:
                        st.error(f"Error reading file: {e}")

# --- TAB 4: DRAFTED PROPOSALS (NEW) ---
with tab_proposals:
    st.subheader("✉️ Drafted Cover Letters")
    
    if "results" in st.session_state:
        results = st.session_state["results"]
        proposals = results.get("proposals", [])
        jobs = results.get("filtered_jobs", [])
        
        if not proposals:
            st.info("No proposals generated yet. (Did any job score high enough?)")
        else:
            # We assume the order of proposals matches the top jobs
            for i, letter in enumerate(proposals):
                # Try to get the matching job title if possible
                job_title = "Unknown Role"
                if i < len(jobs):
                    job_title = f"{jobs[i].title} at {getattr(jobs[i], 'company', 'Unknown')}"
                
                with st.expander(f"Draft #{i+1}: {job_title}", expanded=False):
                    st.text_area("Copy this:", value=letter, height=300)
                    if i < len(jobs):
                         st.caption(f"Apply Link: {jobs[i].url}")
    else:
        st.info("Run the agent to see generated proposals.")                        