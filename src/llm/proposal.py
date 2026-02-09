import os
from typing import List, Dict
from pathlib import Path
from ..models.job import Job

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

# A mock resume profile (In V2, we will load this from a file)
MY_PROFILE = """
I am a Senior Python Developer with 6 years of experience.
Expertise: Python, Django, FastAPI, AWS, and Web Scraping.
GitHub: github.com/pgauin01
"""

def load_profile():
    """Reads the user's profile from profile.md in the root directory."""
    try:
        # Assuming profile.md is in the project root (2 levels up from this file)
        root_dir = Path(__file__).parent.parent.parent
        profile_path = root_dir / "profile.md"
        
        if profile_path.exists():
            return profile_path.read_text(encoding="utf-8")
        else:
            return "A passionate Python Developer with 5 years of experience."
    except Exception:
        return "A passionate Python Developer."

def generate_proposals(jobs: List[Job]) -> Dict[str, str]:
    """
    Generates a cover letter for the top jobs.
    Returns a dict: {job_id: proposal_text}
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    user_profile = load_profile()
    if not api_key or not genai:
        return {}

    client = genai.Client(api_key=api_key)
    proposals = {}

    print(f"✍️  Drafting proposals for {len(jobs)} jobs...")

    for job in jobs:
        prompt = f"""
        You are an expert freelancer applying for a job. Write a concise, professional cover letter.
        
        MY PROFILE:
        {user_profile}
        
        JOB DESCRIPTION:
        Title: {job.title}
        Company: {getattr(job, 'company', 'Unknown')}
        Description: {job.description[:800]}
        
        RULES:
        1. Keep it under 150 words.
        2. Mention specific skills from the description that match my profile.
        3. Do not use placeholders. Sign it with the name found in the profile (or "A Dedicated Developer" if none found).
        """

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            proposals[job.id] = response.text
        except Exception as e:
            print(f"❌ Failed to draft for {job.title}: {e}")
            
    return proposals