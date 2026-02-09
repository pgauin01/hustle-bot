import os
import re

def sanitize_filename(name):
    """Removes weird characters for safe filenames"""
    return re.sub(r'[\\/*?:"<>|]', "", name).replace(" ", "_")

def save_tailored_resume(content, company, role):
    folder = "generated_resumes"
    if not os.path.exists(folder):
        os.makedirs(folder)
        
    safe_company = sanitize_filename(company)
    safe_role = sanitize_filename(role)
    filename = f"{folder}/{safe_company}_{safe_role}.md"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    
    return filename