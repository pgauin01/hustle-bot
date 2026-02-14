import streamlit as st
import os
import json
import pandas as pd
import altair as alt
from datetime import datetime
import time

# --- IMPORTS ---
from src.graph.workflow import create_graph
from src.utils.history import save_to_history, get_history_stats
from src.llm.proposal import generate_proposals
from src.llm.resume_tailor import tailor_resume
from src.utils.file_manager import save_tailored_resume
from src.utils.applications import load_applications, save_application, update_status
from src.models.job import Job
from src.llm.scoring import score_jobs_with_resume
# --- NEW IMPORTS ---
from src.utils.persistence import save_manual_job, load_manual_jobs, delete_manual_job, save_cover_letter, load_cover_letters
from src.utils.google_sheets import log_jobs_to_sheet 

# --- FIX: USE STANDARD GOOGLE LIBRARY ---
try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Page Config
st.set_page_config(page_title="HustleBot 2.7 (Persistent)", page_icon="💼", layout="wide")

# --- HELPER FUNCTIONS ---
def suggest_roles(api_key, skills):
    if not api_key: return []
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = f"Suggest 5 concise job titles for: {skills}. Return comma-separated."
        response = model.generate_content(prompt)
        return [t.strip() for t in response.text.strip().split(",") if t.strip()]
    except: return []

def load_profile():
    if os.path.exists("profile.md"):
        with open("profile.md", "r", encoding="utf-8") as f: return f.read()
    return ""

def save_profile(content):
    with open("profile.md", "w", encoding="utf-8") as f: f.write(content)

# --- INITIALIZE SESSION STATE ---
# This runs once on startup to load your saved data
if "init_done" not in st.session_state:
    # Load Letters
    saved_letters = load_cover_letters()
    for jid, content in saved_letters.items():
        st.session_state[f"cover_letter_{jid}"] = content
    
    # Load Manual Jobs into Results
    manual_jobs = load_manual_jobs()
    if "results" not in st.session_state:
        st.session_state["results"] = {"filtered_jobs": []}
    
    # Merge manual jobs (avoiding duplicates if logic ran twice)
    current_ids = [j.id for j in st.session_state["results"]["filtered_jobs"]]
    for mj in manual_jobs:
        if mj.id not in current_ids:
            st.session_state["results"]["filtered_jobs"].insert(0, mj)
            
    st.session_state["init_done"] = True

# --- SIDEBAR: SETTINGS ---
with st.sidebar:
    st.header("⚙️ Settings")
    with st.expander("🔑 Config", expanded=True):
        if os.path.exists("user_settings.json"):
            with open("user_settings.json", "r") as f: settings = json.load(f)
        else: settings = {}

        api_key = st.text_input("Google API Key", value=settings.get("api_key", ""), type="password")
        sheet_url = st.text_input("Google Sheet URL", value=settings.get("sheet_url", ""))
        tele_token = st.text_input("Telegram Bot Token", value=settings.get("tele_token", ""), type="password")
        tele_chat = st.text_input("Telegram Chat ID", value=settings.get("tele_chat", ""))
        serp_key = st.text_input("SerpApi Key (Optional)", value=settings.get("serp_key", ""), type="password")

        if st.button("💾 Save Settings"):
            with open("user_settings.json", "w") as f:
                json.dump({"api_key": api_key, "sheet_url": sheet_url, "tele_token": tele_token, "tele_chat": tele_chat, "serp_key": serp_key}, f)
            st.success("Saved!")
            st.rerun()

    if api_key: os.environ["GOOGLE_API_KEY"] = api_key
    if sheet_url: os.environ["GOOGLE_SHEET_URL"] = sheet_url
    if tele_token: os.environ["TELEGRAM_BOT_TOKEN"] = tele_token
    if tele_chat: os.environ["TELEGRAM_CHAT_ID"] = tele_chat
    if serp_key: os.environ["SERPAPI_KEY"] = serp_key

st.title("🤖 HustleBot: Career Command Center")

tab_run, tab_manual, tab_jobs, tab_tracker, tab_profile, tab_analytics, tab_docs = st.tabs([
    "🚀 Search", "🕵️ Manual Hunt", "📊 Matches", "📋 Tracker", "👤 Profile", "📈 Insights", "📂 Docs"
])

# --- TAB 1: SEARCH ---
with tab_run:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("🎯 Target")
        if "suggested_role" not in st.session_state: st.session_state["suggested_role"] = "Python Developer"
        query = st.text_input("Job Role", value=st.session_state["suggested_role"])
        keywords = st.text_input("Must-Have Skills", value="Python, Django")
        all_platforms = ["RemoteOK", "WeWorkRemotely",  "Freelancer", "LinkedIn"]
        selected_platforms = st.multiselect("Select Platforms:", options=all_platforms, default=["RemoteOK"])
        
        with st.expander("✨ AI Brainstorm"):
            if st.button("Suggest Roles"):
                st.session_state["role_suggestions"] = suggest_roles(api_key, keywords)
            if "role_suggestions" in st.session_state:
                for r in st.session_state["role_suggestions"]:
                    if st.button(f"📍 {r}"): 
                        st.session_state["suggested_role"] = r
                        st.rerun()
        st.markdown("---")
        run_btn = st.button("🚀 Start Job Hunt", type="primary", use_container_width=True)

    with col2:
        if run_btn:
            st.subheader("⚙️ Log")
            with st.container():
                st.info("Starting Workflow...")
                if not selected_platforms: st.error("Please select at least one platform.")
                else:
                    must_haves = [k.strip() for k in keywords.split(",") if k.strip()]
                    initial_state = {
                        "search_query": query, 
                        "must_have_keywords": must_haves, 
                        "selected_platforms": selected_platforms,
                        "raw_results": [], "normalized_jobs": [], "filtered_jobs": []
                    }
                    try:
                        app = create_graph()
                        final_state = app.invoke(initial_state)
                        
                        # Merge new results with existing manual jobs
                        manual_jobs = load_manual_jobs()
                        fetched_jobs = final_state.get("filtered_jobs", [])
                        final_state["filtered_jobs"] = manual_jobs + fetched_jobs
                        
                        st.session_state["results"] = final_state
                        st.success("✅ Workflow Complete!")
                    except Exception as e: st.error(f"❌ Workflow Failed: {e}")

# --- TAB 2: MANUAL HUNT ---
with tab_manual:
    st.header("🕵️ Manual Job Entry")
    st.caption("Jobs added here are SAVED automatically.")
    
    with st.form("manual_job_form"):
        c1, c2 = st.columns(2)
        m_title = c1.text_input("Job Title", placeholder="e.g. Senior Backend Engineer")
        m_company = c2.text_input("Company Name", placeholder="e.g. Acme Corp")
        m_url = st.text_input("Job URL (Optional)", placeholder="https://...")
        m_desc = st.text_area("Paste Job Description Here", height=300)
        
        submitted = st.form_submit_button("✨ Analyze & Save")
        
        if submitted:
            if not m_title or not m_desc:
                st.error("Please provide at least a Job Title and Description.")
            else:
                with st.spinner("🤖 Analyzing & Saving..."):
                    manual_id = f"manual_{int(time.time())}"
                    new_job = Job(id=manual_id, platform="Manual Entry", title=m_title, company=m_company, description=m_desc, url=m_url, budget_min=0, budget_max=0, is_remote=True)
                    
                    profile_text = load_profile() or "Generic Developer Profile"
                    scored_jobs = score_jobs_with_resume([new_job], profile_text)
                    final_job = scored_jobs[0]
                    
                    # SAVE TO FILE
                    save_manual_job(final_job)
                    
                    # UPDATE SESSION
                    if "results" not in st.session_state: st.session_state["results"] = {"filtered_jobs": []}
                    st.session_state["results"]["filtered_jobs"].insert(0, final_job)
                    
                    st.success(f"✅ Saved! Score: {final_job.relevance_score}/100")

# --- TAB 3: MATCHES ---
with tab_jobs:
    if "results" in st.session_state:
        results = st.session_state["results"]
        jobs = results.get("filtered_jobs", [])
        
        if not jobs:
            st.info("🎉 No jobs found.")
        else:
            st.metric("Qualified Matches", len(jobs))
            for job in jobs:
                score = job.relevance_score
                color = "green" if score >= 80 else "orange" if score >= 50 else "red"
                
                with st.expander(f"**:{color}[{score}/100]** {job.title} @ {getattr(job, 'company', 'Unknown')}"):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**Source:** {job.platform}")
                        st.markdown(f"**Why:** {job.reasoning}")
                        if hasattr(job, 'gap_analysis'): st.info(f"{job.gap_analysis}")
                        st.markdown(f"[🔗 **Link**]({job.url})")

                    with c2:
                        if st.button("✍️ Draft Letter", key=f"cl_{job.id}"):
                            with st.spinner("Generating..."):
                                drafts = generate_proposals([job])
                                content = list(drafts.values())[0]
                                st.session_state[f"cover_letter_{job.id}"] = content
                                # SAVE LETTER
                                save_cover_letter(job.id, content)
                                st.rerun()
                        
                        if st.button("📄 Tailor Resume", key=f"res_{job.id}"):
                            prof = load_profile()
                            if prof:
                                with st.spinner("Tailoring..."):
                                    path = save_tailored_resume(tailor_resume(job, prof), job.company, job.title)
                                    st.session_state[f"resume_{job.id}"] = path
                                    st.rerun()
                            else: st.error("Profile is empty!")
                        
                        if st.button("✅ Track", key=f"trk_{job.id}"):
                            # 1. Save to Local JSON Tracker
                            save_application(job, status="Applied")
                            
                            # 2. Log to Google Sheet (The New Manual Step)
                            sheet_url = os.getenv("GOOGLE_SHEET_URL")
                            if sheet_url:
                                ok = log_jobs_to_sheet([job], sheet_url)
                                if ok:
                                    st.toast("📝 Logged to Google Sheet!")
                                else:
                                    st.error("Sheet Error: Could not log this job. Check credentials/sheet sharing in terminal logs.")
                            else:
                                st.warning("Google Sheet URL is not set, so sheet logging was skipped.")

                            # 3. Remove from "New Matches" view
                            if job.platform == "Manual Entry":
                                delete_manual_job(job.id)
                            else:
                                save_to_history(job.id)
                                
                            st.session_state["results"]["filtered_jobs"] = [j for j in jobs if j.id != job.id]
                            st.rerun()

                        if st.button("❌ Dismiss", key=f"d_{job.id}"):
                            if job.platform == "Manual Entry":
                                delete_manual_job(job.id)
                            else:
                                save_to_history(job.id)
                            st.session_state["results"]["filtered_jobs"] = [j for j in jobs if j.id != job.id]
                            st.rerun()

# --- TAB 4: TRACKER ---
with tab_tracker:
    st.subheader("📋 Application Pipeline")
    apps = load_applications()
    if not apps: st.info("No tracked applications.")
    else:
        apps = sorted(apps, key=lambda x: x["applied_date"], reverse=True)
        for app in apps:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                with c1:
                    st.markdown(f"**{app['title']}**")
                    st.caption(f"{app['company']} | {app['platform']}")
                with c2:
                    st.caption(f"Applied: {app['applied_date']}")
                    st.markdown(f"[Link]({app['url']})")
                with c3:
                    current = app["status"]
                    new = st.selectbox("Status", ["Applied", "Interviewing", "Offer", "Rejected", "Ghosted"], 
                                      index=["Applied", "Interviewing", "Offer", "Rejected", "Ghosted"].index(current),
                                      key=f"stat_{app['id']}", label_visibility="collapsed")
                    if new != current:
                        update_status(app['id'], new)
                        st.rerun()
                with c4:
                    if new == "Interviewing": st.success("🎉")
                    elif new == "Rejected": st.error("💀")

# --- TAB 5: PROFILE ---
with tab_profile:
    st.header("👤 Your Profile")
    current_content = load_profile()
    if not current_content: current_content = "# My Profile\n\n## Skills\n- ..."
    new_content = st.text_area("Edit Profile (Markdown)", value=current_content, height=600)
    if st.button("💾 Save Profile Changes"):
        save_profile(new_content)
        st.success("✅ Saved!")

# --- TAB 6: INSIGHTS ---
with tab_analytics:
    st.subheader("📈 Insights")
    if "results" in st.session_state:
        results = st.session_state["results"]
        jobs = results.get("filtered_jobs", [])
        if jobs:
            data = [{"Platform": j.platform, "Score": j.relevance_score, "Budget": getattr(j, "budget_max", 0)} for j in jobs]
            df = pd.DataFrame(data)
            c1, c2 = st.columns(2)
            with c1: st.bar_chart(df["Score"])
            with c2: st.dataframe(df["Platform"].value_counts())
    else: st.info("Run a search first.")

# --- TAB 7: DOCS ---
with tab_docs:
    st.subheader("📂 Files")
    st.markdown("### 📄 Resumes")
    if os.path.exists("generated_resumes"):
        for f in os.listdir("generated_resumes"):
            with open(f"generated_resumes/{f}") as file:
                st.download_button(f"⬇️ {f}", file.read(), f)
    
    st.divider()
    
    st.markdown("### ✉️ Cover Letters (Saved)")
    # Load from FILE now, not just session
    saved_letters = load_cover_letters()
    for jid, content in saved_letters.items():
        with st.expander(f"Draft for Job ID: {jid}"):
            st.text_area("Content", content, height=200, key=f"view_cl_{jid}")