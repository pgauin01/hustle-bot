import json
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from ..models.job import Job

# Try to import Gemini, fallback if not installed (though requirements.txt has it)
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    pass

def score_jobs_with_resume(jobs, resume_text):
    """
    Compares a list of Job objects against a Resume (Markdown).
    Returns the list with updated .relevance_score, .reasoning, and .gap_analysis.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("⚠️ No API Key found. Skipping AI scoring.")
        return jobs

    # 1. Setup the Brain (Gemini Flash is fast & cheap)
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.1)

    # 2. The "Career Coach" Prompt
    prompt_template = """
    You are an expert Technical Recruiter. 
    I will give you a Candidate Profile and a list of Jobs.
    
    CANDIDATE PROFILE:
    {resume}

    JOBS LIST:
    {jobs_data}

    For each job, provide a JSON object with:
    - "id": The job ID provided.
    - "score": 0-100 (How well the candidate fits).
    - "reasoning": A 1-sentence summary of why (e.g., "Perfect match for Django skills").
    - "gaps": A short string listing MISSING skills or experience (e.g., "Missing AWS and Kubernetes").
    - "advice": A short strategy tip (e.g., "Highlight your side project X to cover the AWS gap").

    Return ONLY a JSON list.
    """
    
    prompt = PromptTemplate(template=prompt_template, input_variables=["resume", "jobs_data"])

    # 3. Batch Process (to save time/money)
    # We send jobs in batches of 5
    batch_size = 5
    scored_jobs = []

    print(f"🧠 AI Analyzing {len(jobs)} jobs against your resume...")

    for i in range(0, len(jobs), batch_size):
        batch = jobs[i : i + batch_size]
        
        # Prepare data for LLM
        jobs_input = json.dumps([
            {"id": j.id, "title": j.title, "description": j.description[:2000]} # Truncate desc to save tokens
            for j in batch
        ])

        try:
            chain = prompt | llm
            response = chain.invoke({"resume": resume_text[:3000], "jobs_data": jobs_input})
            
            # Clean response (remove markdown code blocks if any)
            content = response.content.replace("```json", "").replace("```", "").strip()
            parsed_results = json.loads(content)

            # Map results back to Job objects
            results_map = {str(item["id"]): item for item in parsed_results}

            for job in batch:
                res = results_map.get(str(job.id))
                if res:
                    job.relevance_score = int(res.get("score", 0))
                    job.reasoning = res.get("reasoning", "No reasoning.")
                    # We store the gap analysis in the 'reasoning' or a new attribute if we had one.
                    # Let's pack it into 'reasoning' for now to keep the model simple, or add a dynamic attribute.
                    job.gap_analysis = f"⚠️ Gaps: {res.get('gaps', 'None')}\n💡 Strategy: {res.get('advice', 'None')}"
                scored_jobs.append(job)

        except Exception as e:
            print(f"   ❌ Batch failed: {e}")
            scored_jobs.extend(batch) # Keep original if failed

    return scored_jobs