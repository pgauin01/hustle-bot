import re
from typing import Tuple

def clean_html(raw_html: str) -> str:
    """Removes HTML tags and cleans up whitespace."""
    if not raw_html:
        return ""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', ' ', raw_html)
    # Decode HTML entities (basic)
    clean = clean.replace("&amp;", "&").replace("&nbsp;", " ").replace("&gt;", ">").replace("&lt;", "<")
    # Collapse multiple spaces
    return " ".join(clean.split())

def parse_salary(salary_str: str) -> Tuple[float, float]:
    """
    Attempts to extract min/max salary from a string like '$50k - $80k'.
    Returns (min, max) in USD.
    """
    if not salary_str:
        return 0.0, 0.0
        
    # Simple regex for numbers (e.g., 50000 or 50k)
    # This is a basic implementation; production needs a stronger parser
    matches = re.findall(r'(\d+)[kK]?', salary_str)
    if not matches:
        return 0.0, 0.0
    
    values = []
    for m in matches:
        val = float(m.replace('k', '').replace('K', ''))
        if val < 1000: # Assume 'k' was implied or it's hourly
             # Heuristic: if < 200, assume hourly. If 200-1000, assume 'k' missing? 
             # For now, let's treat '50' as 50000 if it looks like annual, 
             # but to be safe, only multiply if explicitly 'k' was there or logic dictates.
             # Let's keep it simple: 
             pass
        # If 'k' was in the original string, multiply by 1000
        if 'k' in salary_str.lower() and val < 1000:
             val *= 1000
        values.append(val)
        
    if len(values) == 1:
        return values[0], values[0]
    
    return min(values), max(values)