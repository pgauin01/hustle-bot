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

st.set_page_config(page_title="HustleBot", page_icon="💼", layout="wide")

# --- HELPER FUNCTIONS ---
def suggest_roles(skills=""):
    """
    Returns a hardcoded list of targeted AI & Full Stack roles tailored to the user's profile.
    """
    return [
        "Senior Full Stack Engineer",
        "AI Application Engineer",
        "LLM Engineer",
        "Generative AI Engineer",
        "RAG Engineer",
        "AI Product Engineer",
        "AI Systems Engineer",
        "Founding Engineer (AI)",
        "Full Stack AI Engineer",
        "AI Solutions Engineer",
        "Senior Full Stack Engineer",
        "AI Application Engineer",
        "AI Systems Engineer",
        "RAG & LLM Applications Engineer",
        "Generative AI Software Engineer",
    ]
    
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

# --- TAB 1: RUN JOB HUNT ---
with tab_run:
    st.header("🚀 Start Job Hunt")

    # 1. Initialize session state for the Search Query
    if "search_query_input" not in st.session_state:
        st.session_state["search_query_input"] = "Senior Full Stack Engineer"

    # 2. Main Text Input (Tied to the session state via 'key')
    query = st.text_input("Target Job Role", key="search_query_input")

    # 3. ADD THIS BACK: Platform Selection
    available_platforms = ["RemoteOK", "WeWorkRemotely", "Freelancer", "LinkedIn"]
    selected_platforms = st.multiselect(
        "🌐 Target Platforms", 
        options=available_platforms,
        default=available_platforms # Checks all of them by default
    )
    
    # (Notice: The "must_have_skills" input has been deleted here)

    st.markdown("---")

    # 3. Targeted Roles Section (Hardcoded List)
    st.success("👉 **Best fit for you:** Senior Full Stack Engineer | AI Systems | RAG & LLM Applications")
    st.write("### Targeted Roles")
    
    # Get the targeted roles (ensure suggest_roles is updated as we discussed previously)
    roles = suggest_roles() 
    
    # Create a grid of buttons
    cols = st.columns(3)
    for i, role in enumerate(roles):
        # When clicked, update the text input's session state key instantly
        cols[i % 3].button(
            role, 
            key=f"role_btn_{i}", 
            on_click=lambda r=role: st.session_state.update({"search_query_input": r})
        )

    st.markdown("---")

    # 4. RUN JOB HUNT BUTTON
    if st.button("🔍 Run Job Hunt Now"):
        if query:
            if not selected_platforms:
                st.error("⚠️ Please select at least one platform to search.")
            else:
                with st.spinner(f"Hunting for '{query}' across platforms..."):
                    try:
                        from src.graph.workflow import create_graph
                        from src.utils.persistence import log_job_hunt, get_already_saved_ids 
                        
                        seen_ids = get_already_saved_ids()
                        
                        initial_state = {
                            "search_query": query,
                            "must_have_keywords": [], 
                            "selected_platforms": selected_platforms,
                            "raw_results": [],
                            "normalized_jobs": [],
                            "filtered_jobs": [],
                            "seen_job_ids": seen_ids 
                        }
                        
                        app = create_graph()
                        # 1. Capture the results returned by the AI
                        results = app.invoke(initial_state) 
                            
                        log_job_hunt(query) 
                        
                        # 2. INSTANT UI UPDATE: Push new jobs directly into Streamlit's memory
                        new_jobs = results.get("filtered_jobs", [])
                        
                        if "results" in st.session_state:
                            old_jobs = st.session_state["results"].get("filtered_jobs", [])
                            # Put new jobs at the top, followed by old jobs
                            combined = new_jobs + old_jobs 
                            
                            # Deduplicate just in case
                            unique_jobs = {j.id: j for j in combined}.values()
                            st.session_state["results"]["filtered_jobs"] = list(unique_jobs)
                        else:
                            st.session_state["results"] = {"filtered_jobs": new_jobs}
                            
                        st.success("✅ Job Hunt Complete! Matches updated instantly.")
                        time.sleep(1)
                        st.rerun() # Will now instantly show the combined list!
                            
                    except Exception as e:
                        st.error(f"❌ Workflow Crashed: {e}")
        else:
            st.warning("⚠️ Please enter a job role to search for.")

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
    st.header("📊 Job Matches")

    # --- 1. FILTER UI ---
    f_col1, f_col2 = st.columns(2)
    with f_col1:
        min_score = st.slider("🎯 Minimum Relevance Score", min_value=0, max_value=100, value=75, step=5)
    with f_col2:
        date_filter = st.selectbox(
            "📅 Date Posted", 
            ["All Time", "Today", "Last 3 Days", "Last 7 Days", "Last 14 Days"]
        )

    st.markdown("---")

    if "results" in st.session_state:
        results = st.session_state["results"]
        # We rename this to 'all_jobs' to distinguish from the filtered view
        all_jobs = results.get("filtered_jobs", []) 
        
        if not all_jobs:
            st.info("🎉 No pending matches. Run a search or check Tracker.")
        else:
            # --- 2. APPLY FILTERS ---
            display_jobs = []
            for job in all_jobs:
                # Filter by Score
                if job.relevance_score < min_score:
                    continue
                    
                # Filter by Date
                if date_filter != "All Time":
                    posted_date_str = getattr(job, "posted_at", "")
                    if posted_date_str:
                        try:
                            job_date = datetime.strptime(posted_date_str, "%Y-%m-%d").date()
                            today = datetime.now().date()
                            days_diff = (today - job_date).days
                            
                            if date_filter == "Today" and days_diff > 0: continue
                            if date_filter == "Last 3 Days" and days_diff > 3: continue
                            if date_filter == "Last 7 Days" and days_diff > 7: continue
                            if date_filter == "Last 14 Days" and days_diff > 14: continue
                        except ValueError:
                            pass # Skip filtering if date format is weird
                            
                display_jobs.append(job)

            # --- 3. RENDER JOBS ---
            if not display_jobs:
                st.warning("No jobs match your current filters. Try lowering the score or expanding the date range.")
            else:
                st.metric("Visible Matches", len(display_jobs))
                
                for job in display_jobs:
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
                                    save_cover_letter(job.id, content, getattr(job, "company", "Unknown"))
                                    st.rerun()
                            
                            if st.button("📄 Tailor Resume", key=f"res_{job.id}"):
                                prof = load_profile()
                                if prof:
                                    with st.spinner("🔍 Fetching full details & Tailoring..."):
                                        if not job.description or len(job.description) < 100 or "unavailable" in job.description:
                                            print(f"🔄 Re-fetching details for: {job.title} ({job.platform})")
                                            new_desc = smart_fetch_description(job.url)
                                            if new_desc:
                                                job.description = new_desc
                                                print("✅ Successfully fetched fresh description.")
                                            else:
                                                st.warning(f"Could not fetch details from {job.platform}. Resume might be generic.")
                                        
                                        resume_content = tailor_resume(job, prof)
                                        path = save_tailored_resume(resume_content, getattr(job, "company", "Unknown"), job.title)
                                        st.success(f"Generated: {path}")
                                        st.rerun()
                                else: 
                                    st.error("Profile is empty! Update it in the Profile tab.")
                            
                            # --- TRACKING LOGIC ---
                            if st.button("✅ Track", key=f"trk_{job.id}"):
                                save_application(job, "Applied")
                                st.toast("📝 Saved to Tracker!")
                                
                                if job.platform == "Manual Entry":
                                    delete_manual_job(job.id)
                                else:
                                    delete_new_match(job.id)
                                    
                                # CRITICAL FIX: Keep the hidden jobs in the session state!
                                st.session_state["results"]["filtered_jobs"] = [j for j in all_jobs if j.id != job.id]
                                st.rerun()

                            if st.button("❌ Dismiss", key=f"d_{job.id}"):
                                if job.platform == "Manual Entry":
                                    delete_manual_job(job.id)
                                else:
                                    delete_new_match(job.id)
                                    
                                # CRITICAL FIX: Keep the hidden jobs in the session state!
                                st.session_state["results"]["filtered_jobs"] = [j for j in all_jobs if j.id != job.id]
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
    
    # 1. Load ONLY the automated bot matches (Ignore manual jobs entirely)
    fresh_bot_matches = load_new_matches()
    
    # 2. GHOST ROW & MANUAL FILTER
    # Strictly filter out blank rows and double-check that no "Manual Entry" sneaks in
    all_fresh_jobs = [
        j for j in fresh_bot_matches 
        if getattr(j, "title", None) and str(j.title).strip() != "" 
        and str(j.id).strip() != "" 
        and getattr(j, "platform", "") != "Manual Entry"
    ]
    
    if not all_fresh_jobs: 
        st.info("📭 No automated job matches available yet. Run a search to populate your analytics!")
    else:
        # Create the DataFrame
        data = [{"Platform": j.platform, "Score": j.relevance_score, "Job": j.title} for j in all_fresh_jobs]
        df = pd.DataFrame(data)
        
        st.markdown("**📊 Total Automated Jobs by Platform**")
        
        # Group by platform to get exact counts
        platform_counts = df["Platform"].value_counts().reset_index()
        platform_counts.columns = ["Platform", "Count"]
        
        # A beautiful, full-width colored bar chart
        st.bar_chart(platform_counts, x="Platform", y="Count", color="Platform")


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