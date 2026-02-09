import os
import json
from typing import List
from ..models.job import Job

# Try to import Google GenAI, handle if missing
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

def score_jobs_with_llm(jobs: List[Job], query: str) -> List[Job]:
    """
    Sends job descriptions to Gemini to get a relevance score (0-100).
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not genai:
        print("⚠️  Error: 'google-genai' library not installed. Run: pip install google-genai")
        return jobs
    if not api_key:
        print("⚠️  Error: GOOGLE_API_KEY environment variable is missing.")
        return jobs

    print(f"🧠 Scoring {len(jobs)} jobs with AI...")
    
    client = genai.Client(api_key=api_key)
    
    # 1. Prepare Data
    job_payload = []
    for index, j in enumerate(jobs):
        desc = j.description[:400].strip() if j.description else "No description"
        job_payload.append({
            "index": index,
            "title": j.title,
            "company": getattr(j, "company", "Unknown"),
            "description": desc
        })

    prompt = f"""
    You are a strict Recruiter. User Query: "{query}"
    
    Evaluate these jobs using this EXACT SCORING RUBRIC (Total 100pts):
    
    1. **Tech Stack Match (40pts):** Does it list the specific frameworks mentioned in the query?
    2. **Experience Level (30pts):** Does it match a "Senior" profile (5+ years)?
    3. **Clarity & Quality (20pts):** Is the description professional and clear?
    4. **Location/Type (10pts):** Is it Remote/Flexible? (Penalize "On-site" if not stated).
    
    **CRITICAL RULES:**
    - If the job requires "US Citizen" or "Clearance" and the user didn't ask for it -> SCORE 0.
    - If the job is for a different role (e.g., "Data Analyst" vs "Developer") -> SCORE 0.
    
    Input Jobs:
    {json.dumps(job_payload)}
    
    Output JSON Schema:
    {{
        "0": {{ "score": 85, "reason": "Tech: 40/40, Exp: 30/30, Remote: 10/10. Great match." }},
        "1": {{ "score": 20, "reason": "Tech: 0/40 (Java not Python). Score penalized." }}
    }}
    """

    try:
        # 2. Call Gemini
        response = client.models.generate_content(
            model="gemini-2.0-flash", # Updated to latest fast model
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        # 3. Parse Response
        raw_text = response.text or "{}"
        scores = json.loads(raw_text)
        
        # --- CRITICAL FIX START ---
        # If AI returns a List [{}, {}], convert it to Dict {"0": {}, "1": {}}
        if isinstance(scores, list):
            scores = {str(i): item for i, item in enumerate(scores)}
        # --- CRITICAL FIX END ---
        
        # 4. Map back to Job Objects
        updated_count = 0
        for index_str, data in scores.items():
            try:
                idx = int(index_str)
                if 0 <= idx < len(jobs):
                    jobs[idx].relevance_score = data.get("score", 0)
                    jobs[idx].reasoning = data.get("reason", "No reason provided")
                    updated_count += 1
            except ValueError:
                continue

        print(f"✅ AI successfully scored {updated_count}/{len(jobs)} jobs.")
        
        # Sort by score
        jobs.sort(key=lambda x: x.relevance_score, reverse=True)
        return jobs

    except Exception as e:
        print(f"❌ AI Scoring CRASHED: {e}")
        return jobs