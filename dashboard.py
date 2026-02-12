import streamlit as st
import os
import json
import pandas as pd
import altair as alt
from datetime import datetime

# --- IMPORTS ---
from src.graph.workflow import create_graph
from src.utils.history import save_to_history, get_history_stats
from src.llm.proposal import generate_proposals
from src.llm.resume_tailor import tailor_resume
from src.utils.file_manager import save_tailored_resume

# --- FIX: USE STANDARD GOOGLE LIBRARY ---
try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Page Config
st.set_page_config(page_title="HustleBot 2.3", page_icon="💼", layout="wide")

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
    if os.path.exists("profile.md"):
        with open("profile.md", "r", encoding="utf-8") as f: return f.read()
    return None

# --- SIDEBAR ---
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
        
        if st.button("💾 Save Settings"):
            with open("user_settings.json", "w") as f:
                json.dump({"api_key": api_key, "sheet_url": sheet_url, "tele_token": tele_token, "tele_chat": tele_chat}, f)
            st.success("Saved!")
            st.rerun()

    if api_key: os.environ["GOOGLE_API_KEY"] = api_key
    if sheet_url: os.environ["GOOGLE_SHEET_URL"] = sheet_url
    if tele_token: os.environ["TELEGRAM_BOT_TOKEN"] = tele_token
    if tele_chat: os.environ["TELEGRAM_CHAT_ID"] = tele_chat

# --- MAIN PAGE ---
st.title("🤖 HustleBot: Autonomous Recruiter")
st.markdown("### 📡 Active Data Sources")
c1, c2, c3, c4 = st.columns(4)
with c1: st.info("✅ RemoteOK")
with c2: st.info("✅ WeWorkRemotely")
with c3: st.info("✅ Upwork (RSS)")
with c4: st.info("✅ Freelancer.com")
st.markdown("---")

tab_run, tab_jobs, tab_analytics, tab_resumes, tab_letters = st.tabs(["🚀 Run Agent", "📊 Job Matches", "📈 Market Insights", "📝 Tailored Resumes", "✉️ Cover Letters"])

# --- TAB 1: RUN ---
with tab_run:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("🎯 Target")
        if "suggested_role" not in st.session_state: st.session_state["suggested_role"] = "Python Developer"
        query = st.text_input("Job Role", value=st.session_state["suggested_role"])
        keywords = st.text_input("Must-Have Skills", value="Python, Django")
        
        with st.expander("✨ Need help with the role?"):
            if st.button("Brainstorm Roles"):
                st.session_state["role_suggestions"] = suggest_roles(api_key, keywords)
            if "role_suggestions" in st.session_state:
                for role in st.session_state["role_suggestions"]:
                    if st.button(f"📍 {role}"): 
                        st.session_state["suggested_role"] = role
                        st.rerun()
        st.markdown("---")
        run_btn = st.button("🚀 Start Job Hunt", type="primary", use_container_width=True)

    with col2:
        if run_btn:
            st.subheader("⚙️ Execution Log")
            with st.container():
                st.info("Starting Workflow...")
                must_haves = [k.strip() for k in keywords.split(",") if k.strip()]
                initial_state = {"search_query": query, "must_have_keywords": must_haves, "raw_results": [], "normalized_jobs": [], "filtered_jobs": []}
                try:
                    app = create_graph()
                    final_state = app.invoke(initial_state)
                    st.session_state["results"] = final_state
                    st.success("✅ Workflow Complete!")
                except Exception as e: st.error(f"❌ Workflow Failed: {e}")

# --- TAB 2: JOBS ---
with tab_jobs:
    if "results" in st.session_state:
        results = st.session_state["results"]
        jobs = results.get("filtered_jobs", [])
        ignored_count = get_history_stats()
        st.caption(f"🛡️ History Filter Active: {ignored_count} jobs ignored.")

        if not jobs:
            st.info("🎉 No new jobs to review!")
        else:
            st.metric("New Qualified Matches", len(jobs))
            for i, job in enumerate(jobs):
                with st.expander(f"{job.title} @ {getattr(job, 'company', 'Unknown')} ({job.relevance_score}/100)", expanded=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**Platform:** {job.platform}")
                        st.markdown(f"**Why:** {job.reasoning}")
                        st.markdown(f"[🔗 **Apply Now**]({job.url})")
                        status = []
                        if f"cover_letter_{job.id}" in st.session_state: status.append("✅ Letter Ready")
                        if f"resume_{job.id}" in st.session_state: status.append("✅ Resume Ready")
                        if status: st.caption(" | ".join(status))

                    with c2:
                        if st.button("✍️ Draft Letter", key=f"cl_{job.id}"):
                            with st.spinner("Writing..."):
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
                            else: st.error("No profile.md")
                        if st.button("❌ Dismiss", key=f"d_{job.id}"):
                            save_to_history(job.id)
                            st.session_state["results"]["filtered_jobs"] = [j for j in jobs if j.id != job.id]
                            st.rerun()
                        if st.button("✅ Applied", key=f"a_{job.id}"):
                            save_to_history(job.id)
                            st.session_state["results"]["filtered_jobs"] = [j for j in jobs if j.id != job.id]
                            st.rerun()
    else: st.info("Run the agent to see results.")

# --- TAB 3: ANALYTICS (SIMPLIFIED) ---
with tab_analytics:
    st.subheader("📈 Market Insights")
    
    if "results" in st.session_state:
        results = st.session_state["results"]
        jobs = results.get("filtered_jobs", [])
        
        if not jobs:
            st.warning("No data to analyze yet. Run the agent first!")
        else:
            # 1. Prepare Data
            data = []
            for j in jobs:
                score = j.relevance_score
                # Bucket the scores
                if score >= 80: bucket = "🟢 Great Match (80+)"
                elif score >= 50: bucket = "🟡 Good Match (50-79)"
                else: bucket = "🔴 Low Match (<50)"
                
                data.append({
                    "Platform": j.platform,
                    "Score": score,
                    "Quality": bucket,
                    "Budget": getattr(j, "budget_max", 0),
                    "Title": j.title,
                    "Company": getattr(j, "company", "Unknown")
                })
            df = pd.DataFrame(data)

            # 2. KEY METRICS ROW
            m1, m2, m3 = st.columns(3)
            with m1: st.metric("Total Jobs Found", len(df))
            with m2: st.metric("Avg Match Score", f"{df['Score'].mean():.1f}/100")
            
            # Salary Metric (Only for jobs with budget)
            paying_jobs = df[df["Budget"] > 0]
            if not paying_jobs.empty:
                avg_pay = paying_jobs["Budget"].mean()
                with m3: st.metric("Avg Listed Budget", f"${avg_pay:,.0f}")
            else:
                with m3: st.metric("Avg Listed Budget", "N/A")

            st.markdown("---")

            # 3. CHARTS ROW
            c1, c2 = st.columns(2)
            
            # CHART 1: Quality Breakdown (Simple Bar)
            with c1:
                st.markdown("#### 🎯 Match Quality")
                chart_quality = alt.Chart(df).mark_bar().encode(
                    x=alt.X("count()", title="Number of Jobs"),
                    y=alt.Y("Quality", sort=["🟢 Great Match (80+)", "🟡 Good Match (50-79)", "🔴 Low Match (<50)"], title=""),
                    color=alt.Color("Quality", legend=None, scale=alt.Scale(
                        domain=["🟢 Great Match (80+)", "🟡 Good Match (50-79)", "🔴 Low Match (<50)"],
                        range=["#2ecc71", "#f1c40f", "#e74c3c"]
                    )),
                    tooltip=["Quality", "count()"]
                ).properties(height=250)
                st.altair_chart(chart_quality, use_container_width=True)

            # CHART 2: Platforms (Simple Donut)
            with c2:
                st.markdown("#### 🌍 Jobs by Platform")
                chart_platform = alt.Chart(df).mark_arc(innerRadius=60).encode(
                    theta=alt.Theta("count()", stack=True),
                    color=alt.Color("Platform"),
                    tooltip=["Platform", "count()"]
                ).properties(height=250)
                st.altair_chart(chart_platform, use_container_width=True)

            st.markdown("---")

            # 4. TOP PAYING JOBS TABLE (Replaces the complex histogram)
            st.markdown("#### 💰 Top Paying Roles (Listed Budgets)")
            if not paying_jobs.empty:
                # Sort by Budget descending and take top 5
                top_paying = paying_jobs.sort_values(by="Budget", ascending=False).head(5)
                # Display as a clean table
                st.dataframe(
                    top_paying[["Title", "Company", "Budget", "Platform"]],
                    column_config={
                        "Budget": st.column_config.NumberColumn("Budget (Max)", format="$%d")
                    },
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.info("No salary data available in this batch to display.")

    else:
        st.info("Run the agent to see market insights.")

# --- TAB 4: RESUMES ---
with tab_resumes:
    st.subheader("📂 Tailored Resumes")
    if os.path.exists("generated_resumes"):
        files = sorted([f for f in os.listdir("generated_resumes") if f.endswith(".md")], reverse=True)
        for f in files:
            with st.expander(f"📄 {f}"):
                with open(os.path.join("generated_resumes", f), "r", encoding="utf-8") as file: 
                    st.download_button("⬇️ Download", file.read(), f, "text/markdown")

# --- TAB 5: LETTERS ---
with tab_letters:
    st.subheader("✉️ Drafted Letters")
    keys = [k for k in st.session_state.keys() if k.startswith("cover_letter_")]
    for k in keys:
        with st.expander(f"Draft for Job {k.replace('cover_letter_', '')}"):
            st.text_area("Content", st.session_state[k], height=300)