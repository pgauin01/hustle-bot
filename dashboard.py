import streamlit as st
import os
import json
import pandas as pd
import time

# --- IMPORTS ---
from src.graph.workflow import create_graph
from src.utils.history import save_to_history
from src.llm.proposal import generate_proposals
from src.llm.resume_tailor import tailor_resume
from src.utils.file_manager import save_tailored_resume
from src.models.job import Job
from src.llm.scoring import score_jobs_with_resume

# PERSISTENCE IMPORTS
from src.utils.persistence import (
    save_manual_job, 
    load_manual_jobs, 
    delete_manual_job, 
    save_cover_letter, 
    load_cover_letters,
    save_application, 
    load_applications, 
    update_status
)
# NEW MATCHES IMPORTS
from src.utils.google_sheets import log_jobs_to_sheet, load_new_matches, delete_new_match
from datetime import datetime

try:
    import google.generativeai as genai
except ImportError:
    genai = None

st.set_page_config(page_title="HustleBot 2.9 (Fully Persistent)", page_icon="💼", layout="wide")

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
if "init_done" not in st.session_state:
    # UPDATED LOADING LOGIC
    saved_letters = load_cover_letters()
    for jid, data in saved_letters.items():
        # Load just the content string for the text area
        st.session_state[f"cover_letter_{jid}"] = data.get("content", "")
    
    # 1. Load Manual Jobs
    manual_jobs = load_manual_jobs()
    
    # 2. Load New Matches (Bot found)
    bot_matches = load_new_matches()
    
    # 3. Combine them
    all_jobs = manual_jobs + bot_matches
    
    # 4. Remove duplicates
    unique_jobs = {j.id: j for j in all_jobs}.values()
    
    st.session_state["results"] = {"filtered_jobs": list(unique_jobs)}
    st.session_state["init_done"] = True

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Check for secrets/env vars without revealing them
    has_api = bool(os.getenv("GOOGLE_API_KEY") or (hasattr(st, "secrets") and "GOOGLE_API_KEY" in st.secrets))
    has_sheet = bool(os.getenv("GOOGLE_SHEET_URL") or (hasattr(st, "secrets") and "GOOGLE_SHEET_URL" in st.secrets))
    has_creds = bool(os.getenv("GOOGLE_CREDENTIALS_JSON") or (hasattr(st, "secrets") and "GOOGLE_CREDENTIALS_JSON" in st.secrets))
    has_tele = bool(os.getenv("TELEGRAM_BOT_TOKEN") or (hasattr(st, "secrets") and "TELEGRAM_BOT_TOKEN" in st.secrets))

    with st.expander("🔌 Connection Status", expanded=True):
        if has_api:
            st.success("✅ Google Gemini API: Connected")
        else:
            st.error("❌ Google Gemini API: Missing")
            
        if has_sheet and has_creds:
            st.success("✅ Google Sheets: Connected")
        else:
            if not has_sheet: st.error("❌ Sheet URL: Missing")
            if not has_creds: st.error("❌ Service Account: Missing")
            
        if has_tele:
            st.success("✅ Telegram Bot: Connected")
        else:
            st.warning("⚠️ Telegram: Not Configured")

    st.markdown("---")
    
    # Keep the "Reset" or "Clear Cache" button if you want
    if st.button("🔄 Reload App"):
        st.cache_data.clear()
        st.rerun()

    st.info("💡 **Note:** Credentials are managed securely via Streamlit Secrets.")

st.title("🤖 HustleBot: Career Command Center")

# FIND THIS LINE:
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
        all_platforms = ["RemoteOK", "WeWorkRemotely", "Freelancer", "LinkedIn"]
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
                        
                        # Reload everything to show new results
                        manual = load_manual_jobs()
                        bot = load_new_matches()
                        
                        st.session_state["results"] = {"filtered_jobs": manual + bot}
                        st.success("✅ Workflow Complete!")
                        st.rerun()
                    except Exception as e: st.error(f"❌ Workflow Failed: {e}")

# --- TAB 2: MANUAL HUNT ---
with tab_manual:
    st.header("🕵️ Manual Job Entry")
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
                    
                    save_manual_job(final_job)
                    
                    # Add to session immediately
                    if "results" not in st.session_state: st.session_state["results"] = {"filtered_jobs": []}
                    st.session_state["results"]["filtered_jobs"].insert(0, final_job)
                    
                    st.success(f"✅ Saved! Score: {final_job.relevance_score}/100")

# --- TAB 3: MATCHES ---
with tab_jobs:
    if "results" in st.session_state:
        results = st.session_state["results"]
        jobs = results.get("filtered_jobs", [])
        
        if not jobs:
            st.info("🎉 No pending matches. Run a search or check Tracker.")
        else:
            st.metric("Pending Matches", len(jobs))
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
                                
                                # UPDATED SAVE CALL: Pass company name
                                save_cover_letter(job.id, content, getattr(job, "company", "Unknown"))
                                
                                st.rerun()
                        
                        if st.button("📄 Tailor Resume", key=f"res_{job.id}"):
                            prof = load_profile()
                            if prof:
                                with st.spinner("Tailoring..."):
                                    path = save_tailored_resume(tailor_resume(job, prof), job.company, job.title)
                                    st.session_state[f"resume_{job.id}"] = path
                                    st.rerun()
                            else: st.error("Profile is empty!")
                        
                        # --- TRACKING LOGIC ---
                        if st.button("✅ Track", key=f"trk_{job.id}"):
                            save_application(job, "Applied")
                            st.toast("📝 Saved to Tracker!")
                            
                            # DELETE from source sheet
                            if job.platform == "Manual Entry":
                                delete_manual_job(job.id)
                            else:
                                delete_new_match(job.id) # <--- DELETE FROM NEW MATCHES
                                
                            # Update UI
                            st.session_state["results"]["filtered_jobs"] = [j for j in jobs if j.id != job.id]
                            st.rerun()

                        if st.button("❌ Dismiss", key=f"d_{job.id}"):
                            # DELETE from source sheet
                            if job.platform == "Manual Entry":
                                delete_manual_job(job.id)
                            else:
                                delete_new_match(job.id) # <--- DELETE FROM NEW MATCHES
                                
                            st.session_state["results"]["filtered_jobs"] = [j for j in jobs if j.id != job.id]
                            st.rerun()

# --- TAB 4: TRACKER ---
with tab_tracker:
    st.subheader("📋 Application Pipeline")
    apps = load_applications()
    if not apps: st.info("No tracked applications.")
    else:
        try: apps = sorted(apps, key=lambda x: datetime.strptime(str(x.get("Date Applied","")), "%Y-%m-%d"), reverse=True)
        except: pass
        
        for app in apps:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                with c1:
                    st.markdown(f"**{app.get('Title')}**")
                    st.caption(f"{app.get('Company')} | {app.get('Platform')}")
                with c2:
                    st.caption(f"Applied: {app.get('Date Applied')}")
                    st.markdown(f"[Link]({app.get('URL')})")
                with c3:
                    current = app.get("Status", "Applied")
                    options = ["Applied", "Interviewing", "Offer", "Rejected", "Ghosted"]
                    idx = 0
                    if current in options: idx = options.index(current)
                    new = st.selectbox("Status", options, index=idx, key=f"stat_{app.get('ID')}", label_visibility="collapsed")
                    if new != current:
                        update_status(app.get('ID'), new)
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
            data = [{"Platform": j.platform, "Score": j.relevance_score} for j in jobs]
            df = pd.DataFrame(data)
            c1, c2 = st.columns(2)
            with c1: st.bar_chart(df["Score"])
            with c2: st.dataframe(df["Platform"].value_counts())
    else: st.info("Run a search first.")


# --- TAB 6: DOCS (RESUMES & COVER LETTERS) ---
with tab_docs:
    st.header("📂 Career Documents")

    col1, col2 = st.columns(2)

    # --- LEFT COLUMN: RESUMES (Local Files) ---
    with col1:
        st.subheader("📄 Tailored Resumes")
        resume_dir = "generated_resumes"
        
        if not os.path.exists(resume_dir): os.makedirs(resume_dir)
            
        # Get list of .md files
        files = [f for f in os.listdir(resume_dir) if f.endswith(".md")]
        
        if not files:
            st.info("No resumes found.")
        else:
            # Sort by newest
            files.sort(key=lambda x: os.path.getmtime(os.path.join(resume_dir, x)), reverse=True)
            
            for f_name in files:
                file_path = os.path.join(resume_dir, f_name)
                
                # Get date
                t = os.path.getmtime(file_path)
                date_str = datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M')
                
                with st.expander(f"📄 {f_name} ({date_str})"):
                    # Preview
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    st.caption("Preview:")
                    st.code(content[:300] + "...", language="markdown")
                    
                    # Download Markdown Button (PDF removed)
                    st.download_button(
                        label="⬇️ Download Markdown",
                        data=content,
                        file_name=f_name,
                        mime="text/markdown",
                        key=f"dl_md_{f_name}"
                    )

    # --- RIGHT COLUMN: COVER LETTERS (Google Sheets) ---
    with col2:
        st.subheader("✉️ Cover Letters")
        
        letters = load_cover_letters()
        
        if not letters:
            st.info("No cover letters found.")
        else:
            # Loop through the dictionary
            for job_id, data in letters.items():
                company = data.get("company", "Unknown")
                date = data.get("date", "")
                content = data.get("content", "")
                
                # UPDATED LABEL: Shows Company Name
                with st.expander(f"✉️ {company} ({date})"):
                    st.text_area("Content", value=content, height=300, key=f"v_cl_{job_id}")
                    st.info("👉 Ctrl+A, Ctrl+C to copy.")
