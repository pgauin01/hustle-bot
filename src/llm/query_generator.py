import os
import json
from pathlib import Path
from typing import List
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv  


load_dotenv()
openrouter_model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
def load_profile() -> str:
    """Reads the profile.md file."""
    try:
        root_dir = Path(__file__).parent.parent.parent
        profile_path = root_dir / "profile.md"
        if profile_path.exists():
            return profile_path.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""

def generate_search_queries() -> List[str]:
    """
    Analyzes profile.md and returns 3 distinct search queries using a Hybrid Router.
    """
    profile_text = load_profile()
    if not profile_text:
        return ["Python Developer", "Full Stack Engineer", "AI Engineer"]

    active_engine = os.getenv("ACTIVE_LLM", "openrouter").lower()
    
    # 1. SETUP THE HYBRID BRAIN
    if active_engine == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key: return ["Python Developer", "Full Stack", "AI Engineer"]
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)
    else:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key: return ["Python Developer", "Full Stack", "AI Engineer"]
        llm = ChatOpenAI(
            model=openrouter_model,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            default_headers={"HTTP-Referer": "https://github.com/pgauin01/hustle-bot", "X-Title": "HustleBot"},
            temperature=0.2
        )

    # 2. THE UNIFIED PROMPT
    prompt_template = """
    Analyze this candidate profile and generate 3 distinct job search queries.
    
    PROFILE:
    {profile}
    
    RULES:
    1. You MUST return a JSON object with a single key "queries" containing a list of strings.
    2. **CRITICAL: Keep queries SHORT (max 2-3 words).** Search engines fail on long phrases.
    3. Query 1 (Core): High-volume keywords (e.g., "React Node", "Full Stack").
    4. Query 2 (Growth): Emerging tech keywords (e.g., "AI Engineer", "LangChain").
    5. Query 3 (Hybrid): Two skill combos (e.g., "React Python", "Web3 Frontend").
    
    OUTPUT FORMAT:
    {{
        "queries": ["React Node", "Generative AI", "Full Stack"]
    }}
    Return ONLY JSON. No conversational text.
    """
    
    prompt = PromptTemplate(template=prompt_template, input_variables=["profile"])
    chain = prompt | llm

    # 3. EXECUTE
    try:
        response = chain.invoke({"profile": profile_text[:2000]})
        content = getattr(response, "content", "").replace("```json", "").replace("```", "").strip()
        
        # Robust fallback parsing
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            content = content[start:end+1]
            
        parsed = json.loads(content)
        queries = parsed.get("queries", [])
        
        if isinstance(queries, list) and len(queries) > 0:
            return queries
    except Exception as e:
        print(f"Query generation failed: {e}")
        
    return ["Python", "Backend Developer", "Remote Engineer"]