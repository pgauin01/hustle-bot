# 🏛️ HustleBot: System Architecture & User Flows

This document outlines the high-level architecture, module-specific user flows, and data pipelines for **HustleBot**. The system is divided into several autonomous modules orchestrated by LangGraph, operating continuously in the background, alongside a user-facing command center.

---

##  High-Level System Architecture

The macro-view of how HustleBot operates. It runs on a dual-trigger system: **Time-based** (GitHub Actions cron) and **User-initiated** (Streamlit UI).

```mermaid
graph TD
    subgraph Triggers
        Cron[GitHub Actions<br>Every 96 Mins]
        UI[Streamlit Dashboard<br>Manual Search]
    end

    subgraph Orchestration Engine
        LG[LangGraph State Machine]
    end

    subgraph Data Sources
        ROK[RemoteOK API]
        LI[LinkedIn Guest API]
        YC[Y Combinator<br>Playwright]
    end

    subgraph Intelligence
        GEM[Gemini 2.0 Flash<br>Scoring & Matching]
    end

    subgraph Storage & Output
        GS[(Google Sheets CRM)]
        TG[Telegram Notifications]
    end

    Cron -->|Triggers CLI| LG
    UI -->|Triggers Job| LG
    
    LG -->|1. Fetch| ROK & LI & YC
    ROK & LI & YC -->|Raw Data| LG
    
    LG -->|2. Score| GEM
    GEM -->|80+ Matches| LG
    
    LG -->|3. Save| GS
    LG -->|4. Alert| TG
```


##  Module 1: Job Discovery & Scraping Flow
This module is responsible for reaching out to various platforms, bypassing bot protections, and normalizing the disparate HTML/JSON into a standard Job object.
```mermaid
flowchart LR
    Start([Fetch Triggered]) --> CheckState{Check Platforms}
    
    CheckState -->|RemoteOK| API[Query JSON API]
    CheckState -->|LinkedIn| LIG[Query Guest API]
    CheckState -->|YCombinator| PLY[Playwright Headless]
    
    PLY --> Cloudflare{Blocked?}
    Cloudflare -- Yes --> EndYC([Drop / Wait])
    Cloudflare -- No --> Phase1[Extract Job Links]
    Phase1 --> Phase2[Deep Fetch Descriptions]
    
    API & LIG & Phase2 --> Norm[Normalizer Node]
    
    Norm --> Dedup1{Global Dedup<br>Memory Grid}
    Dedup1 -- URL/ID Exists --> Drop([Discard Job])
    Dedup1 -- Unique --> Out([Normalized Jobs Array])
```

##  Module 2: AI Evaluation & Gatekeeper Flow
Once jobs are collected and normalized, they enter the intelligence pipeline. This flow ensures API costs are minimized by dropping bad jobs before they hit the LLM.
```mermaid
flowchart TD
    In([Normalized Jobs]) --> HardFilter{Strict Keyword Check}
    
    HardFilter -- Missing Core Tech --> Drop1([Discard])
    HardFilter -- Tech Matches --> AI[Gemini 2.0 Scoring]
    
    AI --> ReadProf[Read profile.md]
    AI --> Prompt[Apply Strict Prompt<br>Visa/Location Rules]
    Prompt --> Score[Generate 0-100 Score<br>+ Gap Analysis]
    
    Score --> Gatekeeper{Score >= 80?}
    
    Gatekeeper -- No --> Drop2([Discard])
    Gatekeeper -- Yes --> Fresh{Age < 3 Days?}
    
    Fresh -- No --> Drop3([Discard])
    Fresh -- Yes --> Sort[Rank Top 3 Matches]
    Sort --> Out([Elite Jobs Array])
```

##  Module 3: Persistence & Database Flow
To prevent Google Sheets API rate-limiting (429 Quota Exceeded), this module handles the safe, bulk-insertion of jobs into the CRM.
```mermaid
sequenceDiagram
    participant LangGraph
    participant Persistence as Google Sheets Utils
    participant Sheets as Google Sheets API
    
    LangGraph->>Persistence: Pass Elite Jobs Array
    Persistence->>Sheets: get_all_values()
    Sheets-->>Persistence: Return all rows (Memory Grid)
    
    Note over Persistence: Calculate Daily Quota (Max 30)
    
    alt Daily Quota Exceeded
        Persistence-->>LangGraph: Abort (Safety Valve)
    else Quota Available
        Persistence->>Persistence: Shift-Left Duplicate Check (ID & URL)
        Note over Persistence: Format payload to single array
        Persistence->>Sheets: append_rows(value_input_option="RAW")
        Sheets-->>Persistence: 200 OK
        Persistence-->>LangGraph: Success
    end
```
##  Module 4: Dashboard & Manual Hunt Flow
The interactive user flow for the Streamlit dashboard. It allows the user to manually bypass the scrapers and inject a specific job directly into the AI evaluation pipeline.
```mermaid
stateDiagram-v2
    [*] --> Dashboard
    
    state Dashboard {
        MatchesTab : View Automated Matches
        ManualTab : Manual Hunt Entry
        TrackerTab : Track Applications
    }
    
    ManualTab --> Input : User pastes Title, Company, URL, Desc
    Input --> UIDCheck : Generate Hash ID
    
    UIDCheck --> DuplicateCheck
    DuplicateCheck --> Warning : Job Exists in CRM
    Warning --> ManualTab
    
    DuplicateCheck --> AIEval : Unique Job
    AIEval --> Gatekeeper Check
    
    Gatekeeper Check --> Rejected : Score < 80
    Rejected --> ManualTab : Show "Low Score" Error
    
    Gatekeeper Check --> Saved : Score >= 80
    Saved --> MatchesTab : Append to CRM
    
    MatchesTab --> CoverLetter : User clicks "Draft Pitch"
    CoverLetter --> RAG : Gemini generates Letter based on Job + Profile
```

##  Module 5: Telegram Notification Flow
The final step in the automated pipeline. It alerts the user immediately when a high-quality job is secured.

```mermaid
flowchart LR
    In([Elite Jobs Saved]) --> Loop[Iterate Top 3 Jobs]
    
    Loop --> Format[Format HTML Message]
    Format --> AddBadges{Score >= 90?}
    
    AddBadges -- Yes --> Unicorn[Add 🦄 Unicorn Badge]
    AddBadges -- No --> Standard[Add ✅ Standard Badge]
    
    Unicorn & Standard --> AddLink[Embed 'One-Click Apply' URL]
    AddLink --> API[POST /sendMessage]
    
    API --> Telegram((User Mobile App))
    API --> Sleep["time.sleep(1) to avoid API bans"]
    Sleep --> Loop

