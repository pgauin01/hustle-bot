import os
import markdown
from xhtml2pdf import pisa

def ensure_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def save_tailored_resume(content, company, title):
    """
    Saves the resume as both Markdown (.md) and PDF (.pdf).
    Returns the path to the Markdown file (for the dashboard preview).
    """
    ensure_directory("generated_resumes")
    
    # 1. Save Markdown (Original)
    safe_title = f"{company}_{title}".replace(" ", "_").replace("/", "-")
    md_filename = f"generated_resumes/{safe_title}.md"
    pdf_filename = f"generated_resumes/{safe_title}.pdf"
    
    with open(md_filename, "w", encoding="utf-8") as f:
        f.write(content)
        
    # 2. Convert to PDF
    convert_md_to_pdf(content, pdf_filename)
    
    return md_filename

def convert_md_to_pdf(md_content, output_filename):
    """
    Converts Markdown text -> HTML -> PDF.
    """
    # 1. Convert Markdown to HTML
    html_text = markdown.markdown(md_content)
    
    # 2. Add Basic CSS for Resume Styling
    # This makes the PDF look professional (fonts, spacing, etc.)
    styled_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Helvetica, sans-serif; font-size: 12px; line-height: 1.5; color: #333; }}
            h1 {{ color: #2E3E4E; font-size: 24px; border-bottom: 2px solid #2E3E4E; padding-bottom: 5px; margin-top: 0; }}
            h2 {{ color: #2E3E4E; font-size: 18px; margin-top: 20px; margin-bottom: 10px; border-bottom: 1px solid #ccc; }}
            h3 {{ font-size: 14px; color: #555; margin-bottom: 5px; }}
            ul {{ padding-left: 20px; }}
            li {{ margin-bottom: 5px; }}
            p {{ margin-bottom: 10px; }}
        </style>
    </head>
    <body>
        {html_text}
    </body>
    </html>
    """

    # 3. Write PDF
    with open(output_filename, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(styled_html, dest=pdf_file)

    if pisa_status.err:
        print(f"❌ PDF Generation Error: {pisa_status.err}")
    else:
        print(f"✅ PDF Saved: {output_filename}")