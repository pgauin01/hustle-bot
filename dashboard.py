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
from src.models.job import Job  # <--- Needed for Manual Entry
from src.llm.scoring import score_jobs_with_resume # <--- Needed for Manual Scoring

# --- FIX: USE STANDARD GOOGLE LIBRARY ---
try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Page Config
st.set_page_config(page_title="HustleBot 2.6", page_icon="💼", layout="wide")

# --- HELPER FUNCTIONS ---
def suggest_roles(api_key, skills):
    if not api_key: return []
    if not genai: return []
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = f"Suggest 5 concise job titles for: {skills}. Return comma-separated."
        response = model.generate_content(prompt)
        return [t.strip() for t in response.text.strip().split(",") if t.strip()]
    except Exception as e: return []

def load_profile():
    """Loads the base resume from profile.md"""
    if os.path.exists("profile.md"):
        with open("profile.md", "r", encoding="utf-8") as f:
            return f.read()
    return ""

def save_profile(content):
    """Saves updated profile to profile.md"""
    with open("profile.md", "w", encoding="utf-8") as f:
        f.write(content)

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
        
        # New: SERP API Key for Google Jobs
        serp_key = st.text_input("SerpApi Key (Optional)", value=settings.get("serp_key", ""), type="password")

        if st.button("💾 Save Settings"):
            with open("user_settings.json", "w") as f:
                json.dump({
                    "api_key": api_key, 
                    "sheet_url": sheet_url, 
                    "tele_token": tele_token, 
                    "tele_chat": tele_chat,
                    "serp_key": serp_key
                }, f)
            st.success("Saved!")
            st.rerun()

    # Set Environment Variables
    if api_key: os.environ["GOOGLE_API_KEY"] = api_key
    if sheet_url: os.environ["GOOGLE_SHEET_URL"] = sheet_url
    if tele_token: os.environ["TELEGRAM_BOT_TOKEN"] = tele_token
    if tele_chat: os.environ["TELEGRAM_CHAT_ID"] = tele_chat
    if serp_key: os.environ["SERPAPI_KEY"] = serp_key

# --- MAIN PAGE HEADER ---
st.title("🤖 HustleBot: Career Command Center")

# --- TABS ---
# Added "🕵️ Manual Hunt" tab
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
        
        st.markdown("### 📡 Sources")
        all_platforms = ["RemoteOK", "WeWorkRemotely", "Upwork", "Freelancer", "LinkedIn", "GoogleJobs"]
        selected_platforms = st.multiselect("Select Platforms:", options=all_platforms, default=["RemoteOK", "GoogleJobs"])
        
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
                        st.session_state["results"] = final_state
                        st.success("✅ Workflow Complete!")
                    except Exception as e: st.error(f"❌ Workflow Failed: {e}")

# --- TAB 2: MANUAL HUNT (NEW!) ---
with tab_manual:
    st.header("🕵️ Manual Job Entry")
    st.caption("Found a job on LinkedIn or via email? Paste it here to analyze it with AI.")
    
    with st.form("manual_job_form"):
        c1, c2 = st.columns(2)
        m_title = c1.text_input("Job Title", placeholder="e.g. Senior Backend Engineer")
        m_company = c2.text_input("Company Name", placeholder="e.g. Acme Corp")
        m_url = st.text_input("Job URL (Optional)", placeholder="https://...")
        m_desc = st.text_area("Paste Job Description Here", height=300)
        
        submitted = st.form_submit_button("✨ Analyze & Import")
        
        if submitted:
            if not m_title or not m_desc:
                st.error("Please provide at least a Job Title and Description.")
            else:
                with st.spinner("🤖 AI is reading your resume and analyzing this job..."):
                    # 1. Create a Job Object
                    # We generate a unique ID based on time so it doesn't conflict
                    manual_id = f"manual_{int(time.time())}"
                    
                    new_job = Job(
                        id=manual_id,
                        platform="Manual Entry",
                        title=m_title,
                        company=m_company if m_company else "Unknown",
                        description=m_desc,
                        url=m_url if m_url else "#",
                        budget_min=0.0,
                        budget_max=0.0,
                        is_remote=True # Assume remote for safety
                    )
                    
                    # 2. Score it using your Profile
                    profile_text = load_profile()
                    if not profile_text:
                        st.warning("⚠️ No profile found. Scoring based on generic criteria.")
                        profile_text = "Generic Developer Profile"

                    # We reuse the existing scoring logic!
                    scored_jobs = score_jobs_with_resume([new_job], profile_text)
                    final_job = scored_jobs[0]
                    
                    # 3. Add to Session State (Inject it into the list)
                    if "results" not in st.session_state:
                        st.session_state["results"] = {"filtered_jobs": []}
                    
                    # Insert at the TOP of the list
                    current_jobs = st.session_state["results"].get("filtered_jobs", [])
                    current_jobs.insert(0, final_job)
                    st.session_state["results"]["filtered_jobs"] = current_jobs
                    
                    st.success(f"✅ Imported! Match Score: {final_job.relevance_score}/100")
                    st.info("Go to the '📊 Matches' tab to view details and generate cover letters.")

# --- TAB 3: MATCHES ---
with tab_jobs:
    if "results" in st.session_state:
        results = st.session_state["results"]
        jobs = results.get("filtered_jobs", [])
        
        if not jobs:
            st.info("🎉 No new jobs found. Try searching or adding one manually.")
        else:
            st.metric("Qualified Matches", len(jobs))
            for job in jobs:
                # Color Coding
                score = job.relevance_score
                color = "green" if score >= 80 else "orange" if score >= 50 else "red"
                
                with st.expander(f"**:{color}[{score}/100]** {job.title} @ {getattr(job, 'company', 'Unknown')}"):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**Platform:** {job.platform}")
                        st.markdown(f"**Why:** {job.reasoning}")
                        # Display Gap Analysis if available
                        if hasattr(job, 'gap_analysis'):
                            st.info(f"{job.gap_analysis}")
                        st.markdown(f"[🔗 **Job Link**]({job.url})")

                    with c2:
                        # Actions
                        if st.button("✍️ Draft Letter", key=f"cl_{job.id}"):
                            with st.spinner("Generating..."):
                                drafts = generate_proposals([job])
                                st.session_state[f"cover_letter_{job.id}"] = list(drafts.values())[0]
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
                            save_application(job, "Applied")
                            # Don't delete manual jobs from view instantly, simpler UX
                            if job.platform != "Manual Entry":
                                save_to_history(job.id)
                                st.session_state["results"]["filtered_jobs"] = [j for j in jobs if j.id != job.id]
                            st.toast(f"Tracked: {job.title}")
                            st.rerun()

                        if st.button("❌ Dismiss", key=f"d_{job.id}"):
                            if job.platform != "Manual Entry":
                                save_to_history(job.id)
                            st.session_state["results"]["filtered_jobs"] = [j for j in jobs if j.id != job.id]
                            st.rerun()
    else: st.info("Run a search or add a manual job.")

# --- TAB 4: TRACKER ---
with tab_tracker:
    st.subheader("📋 Application Pipeline")
    apps = load_applications()
    
    if not apps:
        st.info("No tracked applications. Go to 'Matches' and click '✅ Track'.")
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
    st.header("👤 Your Profile (The Source of Truth)")
    st.caption("The AI uses this information to score jobs and tailor your resume. Keep it updated!")
    
    current_content = load_profile()
    if not current_content:
        current_content = "# My Profile\n\n## Skills\n- Python\n- ...\n\n## Experience\n- ..."

    new_content = st.text_area("Edit Profile (Markdown)", value=current_content, height=600)
    
    if st.button("💾 Save Profile Changes"):
        save_profile(new_content)
        st.success("✅ Profile updated! Future searches will use this new data.")

# --- TAB 6: INSIGHTS ---
with tab_analytics:
    st.subheader("📈 Market Insights")
    if "results" in st.session_state:
        results = st.session_state["results"]
        jobs = results.get("filtered_jobs", [])
        if jobs:
            data = [{"Platform": j.platform, "Score": j.relevance_score, "Budget": getattr(j, "budget_max", 0)} for j in jobs]
            df = pd.DataFrame(data)
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### Match Quality")
                st.bar_chart(df["Score"])
            with c2:
                st.markdown("#### Platform Distribution")
                st.dataframe(df["Platform"].value_counts())
    else: st.info("Run a search first.")

# --- TAB 7: DOCS ---
with tab_docs:
    st.subheader("📂 Generated Documents")
    
    # 1. Resumes
    st.markdown("### 📄 Tailored Resumes")
    if os.path.exists("generated_resumes"):
        for f in os.listdir("generated_resumes"):
            with open(f"generated_resumes/{f}") as file:
                st.download_button(f"⬇️ {f}", file.read(), f)
    
    st.divider()
    
    # 2. Cover Letters (Session)
    st.markdown("### ✉️ Cover Letters (Session)")
    keys = [k for k in st.session_state.keys() if k.startswith("cover_letter_")]
    for k in keys:
        with st.expander(f"Draft for Job {k.replace('cover_letter_', '')}"):
            st.text_area("Text", st.session_state[k], height=200)