import os
from typing import List, Dict
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from ..models.job import Job
from dotenv import load_dotenv  


load_dotenv()
openrouter_model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
def load_profile():
    """Reads the user's profile from profile.md in the root directory."""
    try:
        root_dir = Path(__file__).parent.parent.parent
        profile_path = root_dir / "profile.md"
        
        if profile_path.exists():
            return profile_path.read_text(encoding="utf-8")
    except Exception:
        pass
    return "A passionate Python Developer with 5 years of experience."

def generate_proposals(jobs: List[Job]) -> Dict[str, str]:
    """
    Generates a cover letter for the top jobs using a Hybrid Router (Gemini or OpenRouter).
    """
    active_engine = os.getenv("ACTIVE_LLM", "openrouter").lower()
    print(f"✍️  Drafting proposals for {len(jobs)} jobs using {active_engine.upper()}...")
    
    # 1. SETUP THE HYBRID BRAIN
    if active_engine == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key: return {}
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0.7)
    else:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key: return {}
        llm = ChatOpenAI(
            model=openrouter_model,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            default_headers={"HTTP-Referer": "https://github.com/pgauin01/hustle-bot", "X-Title": "HustleBot"},
            temperature=0.7
        )

    proposals = {}
    
    # 2. THE UNIFIED PROMPT
    prompt_template = """
    You are an expert freelancer applying for a job. Write a concise, professional cover letter.
    
    MY PROFILE:
    {profile}
    
    JOB DESCRIPTION:
    Title: {title}
    Company: {company}
    Description: {description}
    
    RULES:
    1. Keep it under 150 words.
    2. Mention specific skills from the description that match my profile.
    3. Do not use placeholders. Sign it with the name found in the profile (or "A Dedicated Developer").
    4. Provide ONLY the cover letter text, no conversational filler.
    """
    
    prompt = PromptTemplate(template=prompt_template, input_variables=["profile", "title", "company", "description"])
    chain = prompt | llm

    # 3. EXECUTE
    user_profile = load_profile()
    for job in jobs:
        try:
            response = chain.invoke({
                "profile": user_profile,
                "title": job.title,
                "company": getattr(job, 'company', 'Unknown'),
                "description": (job.description or "")[:800]
            })
            proposals[job.id] = getattr(response, "content", "").strip()
        except Exception as e:
            print(f"❌ Failed to draft for {job.title}: {e}")
            
    return proposals