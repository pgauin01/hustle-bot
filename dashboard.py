import streamlit as st
import os
import json
import pandas as pd
from datetime import datetime

# --- IMPORTS ---
from src.graph.workflow import create_graph
from src.utils.history import save_to_history, get_history_stats
from src.llm.proposal import generate_proposals  # <--- Import Generator

# Try importing Gemini
try:
    from google import genai
except ImportError:
    genai = None

# Page Config
st.set_page_config(page_title="HustleBot 2.3", page_icon="💼", layout="wide")

# --- HELPER: ROLE SUGGESTER ---
def suggest_roles(api_key, skills):
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
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        text = response.text.strip()
        return [t.strip() for t in text.split(",") if t.strip()]
    except Exception as e:
        st.error(f"AI Error: {e}")
        return []

# --- SIDEBAR: SETTINGS ---
with st.sidebar:
    st.header("⚙️ Agent Settings")
    with st.expander("🔑 Config", expanded=True):
        if os.path.exists("user_settings.json"):
            with open("user_settings.json", "r") as f:
                settings = json.load(f)
        else:
            settings = {}

        api_key = st.text_input("Google API Key", value=settings.get("api_key", ""), type="password")
        sheet_url = st.text_input("Google Sheet URL", value=settings.get("sheet_url", ""), placeholder="https://docs.google.com/...")
        tele_token = st.text_input("Telegram Bot Token", value=settings.get("tele_token", ""), type="password")
        tele_chat = st.text_input("Telegram Chat ID", value=settings.get("tele_chat", ""))
        
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

    if api_key: os.environ["GOOGLE_API_KEY"] = api_key
    if sheet_url: os.environ["GOOGLE_SHEET_URL"] = sheet_url
    if tele_token: os.environ["TELEGRAM_BOT_TOKEN"] = tele_token
    if tele_chat: os.environ["TELEGRAM_CHAT_ID"] = tele_chat

# --- MAIN PAGE HEADER ---
st.title("🤖 HustleBot: Autonomous Recruiter")

# Display Active Platforms
st.markdown("### 📡 Active Data Sources")
col1, col2, col3, col4 = st.columns(4)
with col1: st.info("✅ RemoteOK")
with col2: st.info("✅ WeWorkRemotely")
with col3: st.info("✅ Upwork (RSS)")
with col4: st.info("✅ Freelancer.com")

st.markdown("---")

# --- DEFINING TABS ---
# We brought back the "Cover Letters" tab!
tab_run, tab_jobs, tab_resumes, tab_letters = st.tabs(["🚀 Run Agent", "📊 Job Matches", "📝 Tailored Resumes", "✉️ Cover Letters"])

# --- TAB 1: RUN AGENT ---
with tab_run:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("🎯 Target")
        if "suggested_role" not in st.session_state:
            st.session_state["suggested_role"] = "Python Developer"

        query = st.text_input("Job Role", value=st.session_state["suggested_role"])
        keywords = st.text_input("Must-Have Skills", value="Python, Django")
        
        with st.expander("✨ Need help with the role?"):
            if st.button("Brainstorm Roles"):
                if not keywords:
                    st.warning("Enter some skills first!")
                else:
                    with st.spinner("Thinking..."):
                        suggestions = suggest_roles(api_key, keywords)
                        st.session_state["role_suggestions"] = suggestions
            
            if "role_suggestions" in st.session_state and st.session_state["role_suggestions"]:
                st.caption("Click to apply:")
                for role in st.session_state["role_suggestions"]:
                    if st.button(f"📍 {role}", use_container_width=True):
                        st.session_state["suggested_role"] = role
                        st.rerun()

        st.markdown("---")
        run_btn = st.button("🚀 Start Job Hunt", type="primary", use_container_width=True)

    with col2:
        if run_btn:
            st.subheader("⚙️ Execution Log")
            status_container = st.container()
            with status_container:
                st.info("Starting Workflow...")
                must_haves = [k.strip() for k in keywords.split(",") if k.strip()]
                
                initial_state = {
                    "search_query": query,
                    "must_have_keywords": must_haves,
                    "raw_results": [],
                    "normalized_jobs": [],
                    "filtered_jobs": [],
                    # We removed 'proposals' list here because we generate them on-demand now
                }

                try:
                    app = create_graph()
                    final_state = app.invoke(initial_state)
                    st.session_state["results"] = final_state
                    st.success("✅ Workflow Complete!")
                except Exception as e:
                    st.error(f"❌ Workflow Failed: {e}")

# --- TAB 2: JOB MATCHES (With On-Demand Generation) ---
with tab_jobs:
    if "results" in st.session_state:
        results = st.session_state["results"]
        jobs = results.get("filtered_jobs", [])
        
        # Stats
        ignored_count = get_history_stats()
        st.caption(f"🛡️ History Filter Active: {ignored_count} jobs ignored.")

        if not jobs:
            st.info("🎉 No new jobs to review! (All caught up)")
        else:
            st.metric("New Qualified Matches", len(jobs))
            
            for i, job in enumerate(jobs):
                with st.expander(f"{job.title} @ {getattr(job, 'company', 'Unknown')} ({job.relevance_score}/100)", expanded=True):
                    c1, c2 = st.columns([3, 1])
                    
                    with c1:
                        st.markdown(f"**Platform:** {job.platform}")
                        st.markdown(f"**Why:** {job.reasoning}")
                        st.markdown(f"[🔗 **Apply Now**]({job.url})")
                        
                        # --- SHOW DRAFT IF EXISTS ---
                        # Check if we already generated a letter for this job ID
                        letter_key = f"cover_letter_{job.id}"
                        if letter_key in st.session_state:
                            st.success("✅ Cover Letter Drafted!")
                            st.text_area("Copy content:", value=st.session_state[letter_key], height=200, key=f"view_{job.id}")
                    
                    with c2:
                        # --- GENERATE BUTTON ---
                        if st.button("✍️ Draft Letter", key=f"btn_gen_{job.id}"):
                            with st.spinner("Writing..."):
                                try:
                                    # Generate for this single job
                                    # Returns dict: {job_id: "Letter text..."}
                                    drafts = generate_proposals([job])
                                    
                                    # Save to Session State (Memory)
                                    letter_text = list(drafts.values())[0]
                                    st.session_state[f"cover_letter_{job.id}"] = letter_text
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed: {e}")

                        # DISMISS
                        if st.button("❌ Dismiss", key=f"dismiss_{job.id}"):
                            save_to_history(job.id)
                            st.session_state["results"]["filtered_jobs"] = [
                                j for j in st.session_state["results"]["filtered_jobs"] if j.id != job.id
                            ]
                            st.toast(f"Dismissed: {job.title}")
                            st.rerun()

                        # APPLIED
                        if st.button("✅ Applied", key=f"apply_{job.id}"):
                            save_to_history(job.id)
                            st.session_state["results"]["filtered_jobs"] = [
                                j for j in st.session_state["results"]["filtered_jobs"] if j.id != job.id
                            ]
                            st.toast(f"Applied: {job.title}")
                            st.rerun()
    else:
        st.info("Run the agent to see results.")

# --- TAB 3: TAILORED RESUMES ---
with tab_resumes:
    st.subheader("📂 Generated Resumes")
    folder_path = "generated_resumes"
    if os.path.exists(folder_path):
        files = [f for f in os.listdir(folder_path) if f.endswith(".md")]
        if not files:
            st.info("No resumes generated yet.")
        else:
            for filename in files:
                file_path = os.path.join(folder_path, filename)
                with st.expander(f"📄 {filename}", expanded=False):
                    try:
                        with open(file_path, "r", encoding="utf-8") as f: content = f.read()
                        st.download_button("⬇️ Download Markdown", content, filename, "text/markdown")
                        st.code(content[:500] + "...", language="markdown") 
                    except Exception as e: st.error(f"Error: {e}")
    else:
        st.warning("No 'generated_resumes' folder found.")

# --- TAB 4: COVER LETTERS (The Archive) ---
with tab_letters:
    st.subheader("✉️ Your Drafts (Session)")
    
    # scan session state for any keys starting with "cover_letter_"
    draft_keys = [k for k in st.session_state.keys() if k.startswith("cover_letter_")]
    
    if not draft_keys:
        st.info("No cover letters generated in this session yet. Go to 'Job Matches' and click '✍️ Draft Letter' on a job!")
    else:
        for key in draft_keys:
            # Extract ID to find job details (optional, but we just show the ID for now)
            job_id = key.replace("cover_letter_", "")
            content = st.session_state[key]
            
            with st.expander(f"Draft for Job ID: {job_id}", expanded=True):
                st.text_area("Content", value=content, height=300, key=f"archive_{key}")
                st.caption("Copy and paste this into the job application.")