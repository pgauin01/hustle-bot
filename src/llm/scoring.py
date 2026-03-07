import json
import os
import time
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from ..models.job import Job
from dotenv import load_dotenv  


load_dotenv()
openrouter_model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

def _extract_json_results(content):
    """Robust parser for {"results": [...]} output from either model."""
    if not content:
        return []

    text = str(content)
    cleaned = text.replace("```json", "").replace("```", "").strip()
    
    try:
        parsed = json.loads(cleaned)
        return parsed.get("results", []) if isinstance(parsed, dict) else []
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return []
        try:
            parsed = json.loads(cleaned[start : end + 1])
            return parsed.get("results", []) if isinstance(parsed, dict) else []
        except json.JSONDecodeError:
            return []

def _apply_batch_results(batch, parsed_results):
    results_map = {
        str(item.get("id")): item
        for item in parsed_results
        if isinstance(item, dict) and item.get("id") is not None
    }

    for job in batch:
        res = results_map.get(str(job.id))
        if not res:
            continue
        try:
            job.relevance_score = int(res.get("score", 0))
        except Exception:
            job.relevance_score = 0
        job.reasoning = res.get("reasoning", "No reasoning.")
        job.gap_analysis = (
            f"Gaps: {res.get('gaps', 'None')}\n"
            f"Strategy: {res.get('advice', 'None')}"
        )

def _score_batch_with_retry(chain, resume_text, batch, max_attempts, desc_limit):
    jobs_input = json.dumps(
        [
            {
                "id": j.id,
                "title": j.title,
                "description": (j.description or "")[:desc_limit],
            }
            for j in batch
        ]
    )

    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = chain.invoke(
                {"resume": (resume_text or ""), "jobs_data": jobs_input}
            )
            parsed_results = _extract_json_results(getattr(response, "content", ""))
            if not parsed_results:
                raise ValueError("Model returned empty or invalid JSON.")
            _apply_batch_results(batch, parsed_results)
            return True
        except Exception as e:
            last_error = e
            if attempt < max_attempts:
                backoff = min(8, 2 ** (attempt - 1))
                print(f"   [retry] Batch retry {attempt}/{max_attempts - 1} in {backoff}s: {e}")
                time.sleep(backoff)

    print(f"   [failed] Batch failed after {max_attempts} attempts: {last_error}")
    return False

def score_jobs_with_resume(jobs, resume_text):
    """
    Compares a list of Job objects against a Resume using a Hybrid Router (Gemini or OpenRouter).
    """
    if not jobs:
        return []

    # 1. SETUP THE HYBRID BRAIN
    active_engine = os.getenv("ACTIVE_LLM", "openrouter").lower()
    print(f"[ai] Analyzing {len(jobs)} jobs using {active_engine.upper()}...")

    if active_engine == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("[warning] No GOOGLE_API_KEY found. Skipping AI scoring.")
            return jobs
            
        model_name = os.getenv("GEMINI_SCORING_MODEL", "gemini-2.5-flash")
        request_timeout = float(os.getenv("GEMINI_REQUEST_TIMEOUT", "45"))
        llm_retries = int(os.getenv("GEMINI_RETRIES", "2"))
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.0,
            request_timeout=request_timeout,
            retries=llm_retries,
        )
    else:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            print("[warning] No OPENROUTER_API_KEY found. Skipping AI scoring.")
            return jobs
            
        llm = ChatOpenAI(
            model=openrouter_model,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            default_headers={"HTTP-Referer": "https://github.com/pgauin01/hustle-bot", "X-Title": "HustleBot"},
            temperature=0.0
        )

    # 2. THE STRICT RECRUITER PROMPT
    prompt_template = """
    You are an expert, highly critical Technical Recruiter.
    I will give you a Candidate Profile and a list of Jobs.

    CANDIDATE PROFILE:
    {resume}

    JOBS LIST:
    {jobs_data}

    YOUR SCORING RULES:
    1. Base Score: Start at 100.
    2. Location & Timezone Penalty: The candidate lives in India (IST). If the job requires "Hybrid", "On-Site", or mentions US-specific timezones for core hours (e.g., "ET hours", "PST", "EST"), DEDUCT 80 POINTS immediately.
    3. Implicit US-Only Penalty: If a job is marked "Remote" but lists a specific US city/state as the location without explicitly stating "Global Remote", DEDUCT 80 POINTS.
    4. Tech Stack Penalty: If the job explicitly requires a core language/framework (like C#, .NET, Java, Azure) that is entirely missing from the candidate's resume, DEDUCT 50 POINTS.
    5. Reward: Only give scores above 80 if the candidate matches BOTH the core backend stack AND the AI requirements.
    6. Visa & Contract Penalty: If the job description contains ANY of the following phrases, DEDUCT 100 POINTS immediately:
       - "US Citizen" or "Green Card required"
       - "W2 Only" or "No C2C" (Corp-to-Corp)
       - "No Visa Sponsorship" or "Must be authorized to work in the US without sponsorship"
       - "Clearance required" (e.g., Secret, Top Secret)

    OUTPUT FORMAT:
    You MUST return a valid JSON object with a single key "results" containing a list of evaluated jobs.
    {{
        "results": [
            {{
                "id": "job_123",
                "score": 85,
                "reasoning": "Strong match for Python, but missing AWS.",
                "gaps": "AWS, CI/CD",
                "advice": "Highlight your FastAPI projects."
            }}
        ]
    }}
    Return ONLY the JSON. No conversational text.
    """

    prompt = PromptTemplate(template=prompt_template, input_variables=["resume", "jobs_data"])
    chain = prompt | llm

    # 3. Batch Process 
    batch_size = int(os.getenv("GEMINI_BATCH_SIZE", "4"))
    batch_attempts = int(os.getenv("GEMINI_BATCH_ATTEMPTS", "3"))
    scored_jobs = []

    for i in range(0, len(jobs), batch_size):
        batch = jobs[i : i + batch_size]
        ok = _score_batch_with_retry(
            chain=chain,
            resume_text=resume_text, 
            batch=batch,
            max_attempts=batch_attempts,
            desc_limit=5000, 
        )

        if not ok and len(batch) > 1:
            print(f"   [fallback] Single-job scoring for {len(batch)} jobs.")
            for job in batch:
                _score_batch_with_retry(
                    chain=chain,
                    resume_text=resume_text,
                    batch=[job],
                    max_attempts=2,
                    desc_limit=5000, 
                )

        scored_jobs.extend(batch)

    return scored_jobs