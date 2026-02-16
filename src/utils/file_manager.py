import os

def ensure_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def save_tailored_resume(content, company, title):
    """
    Saves the resume as Markdown (.md) only.
    Returns the path to the Markdown file.
    """
    ensure_directory("generated_resumes")
    
    # Create a safe filename
    safe_title = f"{company}_{title}".replace(" ", "_").replace("/", "-")
    md_filename = f"generated_resumes/{safe_title}.md"
    
    # Write the file
    with open(md_filename, "w", encoding="utf-8") as f:
        f.write(content)
        
    return md_filename

def delete_resume(filename):
    """
    Deletes a specific resume file from the 'generated_resumes' folder.
    """
    try:
        file_path = os.path.join("generated_resumes", filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception as e:
        print(f"❌ Error deleting resume: {e}")
        return False