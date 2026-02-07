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
    if not api_key or not genai:
        print("⚠️ No API Key or SDK found. Skipping AI scoring.")
        return jobs

    print(f"🧠 Scoring {len(jobs)} jobs with AI...")
    
    client = genai.Client(api_key=api_key)
    
    # Prepare a compact list for the prompt to save tokens
    job_summaries = []
    for j in jobs:
        # Limit description length to avoid huge prompts
        desc_preview = j.description[:400] + "..." if len(j.description) > 400 else j.description
        job_summaries.append({
            "id": j.id,
            "title": j.title,
            "description": desc_preview,
            "skills": j.skills
        })

    prompt = f"""
    You are a career assistant for a Developer. 
    User Query: "{query}"
    
    Analyze these jobs. Return a JSON object mapping Job IDs to a score (0-100) and a short reasoning.
    
    Rules:
    - Score < 30: Irrelevant, spam, or totally wrong stack.
    - Score > 80: Perfect match for the query.
    
    Input Jobs:
    {json.dumps(job_summaries)}
    
    Output JSON Schema:
    {{
        "job_id_1": {{ "score": 85, "reason": "Good match" }},
        "job_id_2": {{ "score": 10, "reason": "Wrong language" }}
    }}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        # Parse the JSON response
        scores = json.loads(response.text)
        
        # Apply scores back to Job objects
        scored_jobs = []
        for job in jobs:
            if job.id in scores:
                data = scores[job.id]
                job.relevance_score = data.get("score", 0)
                job.reasoning = data.get("reason", "No reason provided")
            scored_jobs.append(job)
            
        # Sort by highest score
        scored_jobs.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored_jobs

    except Exception as e:
        print(f"❌ AI Scoring failed: {e}")
        return jobs