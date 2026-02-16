import os
import google.generativeai as genai
from ..models.job import Job

def tailor_resume(job : Job, profile_content:str) -> str:
    """
    Tailors the resume using Gemini.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return profile_content  # Fallback if no API key

    # 1. Check if we actually have job details
    if not job.description or len(job.description) < 50:
        print(f"⚠️ Warning: Job description for {job.title} is empty or too short.")
        # We still run it, but we know it will be generic.

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-pro")
        
        # 2. STRICT PROMPT
        prompt = f"""
        You are an expert Resume Writer. 
        Your task is to tailor the following resume for the specific job description provided.
        
        JOB TITLE: {job.title} at {job.company}
        JOB DESCRIPTION: 
        {job.description}
        
        CANDIDATE PROFILE:
        {profile_content}
        
        RULES:
        1. Return ONLY the markdown content. 
        2. DO NOT include any introductory text like "Here is the resume" or "I have optimized...".
        3. Start directly with the header (e.g., "# Name").
        4. Optimize keywords for ATS based on the job description.
        """
        
        response = model.generate_content(prompt)
        content = response.text
        
        # 3. CLEANUP LOGIC (The Fix)
        # If the AI still adds chatty text, we strip everything before the first header.
        if "# " in content:
            # Keep everything starting from the first header
            content = content[content.find("# "):]
            
        return content

    except Exception as e:
        print(f"❌ Resume Tailoring Error: {e}")
        return profile_content