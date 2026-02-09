# src/models/job.py
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

@dataclass
class Job:
    id: str                 # Unique ID (e.g., URL or Platform ID)
    platform: str           # "upwork", "remoteok", "weworkremotely"
    title: str
    description: str        # Cleaned text (no HTML)
    url: str
    budget_min: float = 0.0 # Normalized to USD
    budget_max: float = 0.0 # Normalized to USD
    currency: str = "USD"
    skills: List[str] = field(default_factory=list)
    posted_at: Optional[datetime] = None

    # NEW FIELDS
    location: str = "Unknown"  # e.g., "Worldwide", "United States", "India"
    is_remote: bool = True
    
    # Analysis fields (filled by AI later)
    relevance_score: int = 0
    reasoning: str = ""
    company: str = "Unknown"