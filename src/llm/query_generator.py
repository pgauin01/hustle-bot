import os
import json
from pathlib import Path
from typing import List

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

def load_profile() -> str:
    """Reads the profile.md file."""
    try:
        # Adjust path as needed to find profile.md in root
        root_dir = Path(__file__).parent.parent.parent
        profile_path = root_dir / "profile.md"
        if profile_path.exists():
            return profile_path.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""

def generate_search_queries() -> List[str]:
    """
    Analyzes profile.md and returns 3 distinct search queries.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    profile_text = load_profile()
    
    if not api_key or not genai or not profile_text:
        return ["Python Developer", "Full Stack Engineer", "AI Engineer"]

    client = genai.Client(api_key=api_key)
    
    # ... inside generate_search_queries function ...

    prompt = f"""
    Analyze this candidate profile and generate 3 distinct job search queries.
    
    PROFILE:
    {profile_text[:2000]}
    
    RULES:
    1. Return strictly a JSON list of strings.
    2. Query 1: **CORE STACK** (Focus on the candidate's strongest hard skills, e.g., "React Developer", "Frontend Engineer").
    3. Query 2: **CAREER GROWTH** (Focus on their new/emerging skills, e.g., "AI Engineer", "Web3 Developer").
    4. Query 3: **HYBRID/UNICORN** (Combine both, e.g., "React AI Developer", "Full Stack Web3").
    
    Output Format: ["Query 1", "Query 2", "Query 3"]
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Query generation failed: {e}")
        return ["Python", "Backend Developer", "Remote Engineer"]