import json
import os
import time
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from ..models.job import Job


def _extract_json_list(content):
    """Best-effort parser for model output that should contain a JSON list."""
    if not content:
        return []

    if isinstance(content, list):
        text = " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    else:
        text = str(content)

    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return []
        try:
            parsed = json.loads(cleaned[start : end + 1])
            return parsed if isinstance(parsed, list) else []
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
                {"resume": (resume_text or "")[:2200], "jobs_data": jobs_input}
            )
            parsed_results = _extract_json_list(getattr(response, "content", ""))
            if not parsed_results:
                raise ValueError("Model returned empty or invalid JSON list.")
            _apply_batch_results(batch, parsed_results)
            return True
        except Exception as e:
            last_error = e
            if attempt < max_attempts:
                backoff = min(8, 2 ** (attempt - 1))
                print(
                    f"   [retry] Batch retry {attempt}/{max_attempts - 1} in {backoff}s: {e}"
                )
                time.sleep(backoff)

    print(f"   [failed] Batch failed after {max_attempts} attempts: {last_error}")
    return False


def score_jobs_with_resume(jobs, resume_text):
    """
    Compares a list of Job objects against a Resume (Markdown).
    Returns the list with updated .relevance_score, .reasoning, and .gap_analysis.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[warning] No API Key found. Skipping AI scoring.")
        return jobs

    # 1. Setup the Brain (Gemini Flash is fast & cheap)
    model_name = os.getenv("GEMINI_SCORING_MODEL", "gemini-2.5-flash")
    request_timeout = float(os.getenv("GEMINI_REQUEST_TIMEOUT", "45"))
    llm_retries = int(os.getenv("GEMINI_RETRIES", "2"))
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0.1,
        request_timeout=request_timeout,
        retries=llm_retries,
    )

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
    chain = prompt | llm

    # 3. Batch Process (to save time/money)
    batch_size = int(os.getenv("GEMINI_BATCH_SIZE", "4"))
    batch_attempts = int(os.getenv("GEMINI_BATCH_ATTEMPTS", "3"))
    scored_jobs = []

    print(f"[ai] Analyzing {len(jobs)} jobs against your resume...")

    for i in range(0, len(jobs), batch_size):
        batch = jobs[i : i + batch_size]
        ok = _score_batch_with_retry(
            chain=chain,
            resume_text=resume_text,
            batch=batch,
            max_attempts=batch_attempts,
            desc_limit=1200,
        )

        # If a larger batch fails entirely, try each job individually.
        if not ok and len(batch) > 1:
            print(f"   [fallback] Single-job scoring for {len(batch)} jobs.")
            for job in batch:
                _score_batch_with_retry(
                    chain=chain,
                    resume_text=resume_text,
                    batch=[job],
                    max_attempts=2,
                    desc_limit=900,
                )

        scored_jobs.extend(batch)

    return scored_jobs
