import streamlit as st
import os
import json
import pandas as pd
import time
import requests
from bs4 import BeautifulSoup

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
    delete_cover_letter,
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
def suggest_roles(skills):
    """
    Suggests job titles based on skills using Gemini.
    Automatically finds the API key from Secrets or Env.
    """
    # 1. Get API Key
    api_key = None
    if hasattr(st, "secrets") and "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
    elif os.getenv("GOOGLE_API_KEY"):
        api_key = os.getenv("GOOGLE_API_KEY")
        
    if not api_key:
        st.error("❌ Google API Key is missing. Add it to Secrets.")
        return []

    try:
        # 2. Configure Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-pro")
        
        # 3. Generate
        prompt = f"Suggest 5 concise job titles for someone with these skills: {skills}. Return ONLY the titles, separated by commas."
        response = model.generate_content(prompt)
        
        # 4. Parse
        if response.text:
            return [t.strip() for t in response.text.strip().split(",") if t.strip()]
        return []
    except Exception as e:
        st.error(f"AI Error: {e}")
        return []
    
def smart_fetch_description(url):
    """
    Attempts to fetch job description text from ANY url.
    """
    try:
        # 1. Use a browser-like User-Agent to avoid getting blocked
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 2. Cleanup: Remove scripts, styles, and navbars
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # 3. Get text and limit length (Gemini has a limit)
            text = soup.get_text(separator="\n")
            
            # Clean up extra whitespace
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            clean_text = "\n".join(lines)
            
            return clean_text[:8000] # Return first 8000 chars
    except Exception as e:
        print(f"❌ Smart Fetch Error: {e}")
    
    return ""    

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
                st.session_state["role_suggestions"] = suggest_roles(keywords)
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
                                with st.spinner("🔍 Fetching full details & Tailoring..."):
                                    
                                    # --- UNIVERSAL RE-FETCH LOGIC ---
                                    # Check if description is missing, short, or the placeholder
                                    if not job.description or len(job.description) < 100 or "unavailable" in job.description:
                                        print(f"🔄 Re-fetching details for: {job.title} ({job.platform})")
                                        
                                        # Try to get real text from the URL
                                        new_desc = smart_fetch_description(job.url)
                                        
                                        if new_desc:
                                            job.description = new_desc
                                            print("✅ Successfully fetched fresh description.")
                                        else:
                                            st.warning(f"Could not fetch details from {job.platform}. Resume might be generic.")
                                    
                                    # --- PROCEED WITH TAILORING ---
                                    # Now job.description has the real text (if fetch worked)
                                    resume_content = tailor_resume(job, prof)
                                    
                                    # Save
                                    path = save_tailored_resume(resume_content, getattr(job, "company", "Unknown"), job.title)
                                    
                                    st.success(f"Generated: {path}")
                                    st.rerun()
                            else: 
                                st.error("Profile is empty! Update it in the Profile tab.")
                        
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
    
    # Refresh button (useful after manual edits)
    if st.button("🔄 Refresh List"):
        st.rerun()

    col1, col2 = st.columns(2)

    # --- LEFT COLUMN: RESUMES (Local Files) ---
    with col1:
        st.subheader("📄 Tailored Resumes")
        resume_dir = "generated_resumes"
        if not os.path.exists(resume_dir): os.makedirs(resume_dir)
            
        files = [f for f in os.listdir(resume_dir) if f.endswith(".md")]
        
        if not files:
            st.info("No resumes found.")
        else:
            files.sort(key=lambda x: os.path.getmtime(os.path.join(resume_dir, x)), reverse=True)
            
            for f_name in files:
                file_path = os.path.join(resume_dir, f_name)
                t = os.path.getmtime(file_path)
                date_str = datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M')
                
                with st.expander(f"📄 {f_name} ({date_str})"):
                    # Preview
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    st.caption("Preview:")
                    st.code(content[:300] + "...", language="markdown")
                    
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        st.download_button("⬇️ Download", content, f_name)
                    with c2:
                        # DELETE BUTTON
                        if st.button("🗑️ Delete", key=f"del_res_{f_name}"):
                            from src.utils.file_manager import delete_resume
                            if delete_resume(f_name):
                                st.success(f"Deleted {f_name}")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error("Failed to delete.")

    # --- RIGHT COLUMN: COVER LETTERS (Google Sheets) ---
    with col2:
        st.subheader("✉️ Cover Letters")
        letters = load_cover_letters()
        
        if not letters:
            st.info("No cover letters found.")
        else:
            for job_id, data in letters.items():
                company = data.get("company", "Unknown")
                date = data.get("date", "")
                content = data.get("content", "")
                
                with st.expander(f"✉️ {company} ({date})"):
                    st.text_area("Content", value=content, height=200, key=f"v_cl_{job_id}")
                    
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        st.info("👉 Ctrl+A, Ctrl+C to copy")
                    with c2:
                        # DELETE BUTTON
                        if st.button("🗑️ Delete", key=f"del_cl_{job_id}"):
                            if delete_cover_letter(job_id):
                                st.success(f"Deleted letter for {company}")
                                time.sleep(1) # Give API time to sync
                                st.rerun()
                            else:
                                st.error("Failed to delete.")