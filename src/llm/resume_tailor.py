import os
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from ..models.job import Job

def tailor_resume(job: Job, base_resume: str) -> str:
    """
    Rewrites the base resume to highlight skills relevant to the specific job.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro", # Use Pro for better writing
        google_api_key=api_key,
        temperature=0.3
    )

    prompt = PromptTemplate.from_template("""
    You are an expert Resume Writer & ATS Optimizer.
    
    JOB DESCRIPTION:
    {job_description}
    
    CANDIDATE PROFILE (Markdown):
    {profile}
    
    TASK:
    Rewrite the Candidate Profile to target this specific job.
    1. SUMMARY: Rewrite the professional summary to mention the specific role title and matching keywords.
    2. SKILLS: Re-order technical skills so the ones mentioned in the Job Description appear FIRST.
    3. BULLET POINTS: Tweak the experience bullet points to use the same terminology as the JD (e.g., if JD says "Restful Services", change "API" to "Restful Services").
    4. Do NOT invent lies. Only rephrase existing experience.
    5. Keep the Markdown format.
    
    OUTPUT:
    The full tailored markdown resume.
    """)

    try:
        chain = prompt | llm
        response = chain.invoke({
            "job_description": job.description[:5000], # Truncate to fit context
            "profile": base_resume
        })
        return response.content
    except Exception as e:
        print(f"❌ Resume Tailoring Failed: {e}")
        return base_resume # Fallback to original