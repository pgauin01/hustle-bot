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
        
        # 2. SURGICAL PROMPT
        prompt = f"""
        You are an expert Executive Technical Recruiter. 
        Your task is to subtly tailor the candidate's highly-optimized resume for the specific job description below.
        
        JOB TITLE: {job.title} at {job.company}
        JOB DESCRIPTION: 
        {job.description}
        
        CANDIDATE PROFILE:
        {profile_content}
        
        CRITICAL RULES (DO NOT IGNORE):
        1. DO NOT REWRITE THE WHOLE RESUME. 
        2. DO NOT DELETE METRICS: You must perfectly preserve all hard numbers, API request counts, user counts, and percentages from the original profile.
        3. DO NOT DELETE PROJECTS: Keep "HustleBot", "Shadow AI", and all specific frameworks mentioned.
        4. SURGICAL TWEAKS ONLY: 
           - Rewrite the "PROFESSIONAL SUMMARY" slightly so it directly mentions the Company Name and their core product/mission.
           - Reorder the "SKILLS" list so the exact keywords from the Job Description appear first.
           - Reorder the bullet points under Work Experience so the most relevant achievements are at the top.
        5. Return ONLY the raw Markdown content. DO NOT include conversational text. Start immediately with the "# Praful Gaur" header.
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