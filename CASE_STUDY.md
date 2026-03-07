# 🧠 Engineering Case Study: Building HustleBot

Building a fully autonomous AI agent that runs 24/7 without getting banned or bankrupting me on API costs presented several unique engineering challenges. Here is how I solved them.

### Challenge 1: Bypassing Enterprise Bot Protection (Cloudflare)
**The Problem:** Modern job boards like Wellfound and Y Combinator use aggressive bot protection (Cloudflare, DataDome) that instantly blocks standard `requests` or basic Selenium scripts.
**The Solution:** I implemented a two-phase Playwright extraction strategy. First, I use a headless Chromium instance to navigate the React SPA and trigger lazy loading. Instead of relying on brittle CSS selectors, I use resilient regex and DOM traversal to extract raw job URLs. Second, I perform a "Deep Fetch" loop with custom timeout handling (`PlaywrightTimeoutError`) to snatch the DOM text even if heavy tracking scripts fail to load.

### Challenge 2: LLM Rate Limiting and Failover Architecture
**The Problem:** Relying on a single LLM provider (like Google Gemini) creates a single point of failure. If the free tier hits a `429 Rate Limit` during a 150-job batch, the entire pipeline crashes.
**The Solution:** I built a **Hybrid AI Router**. The LangGraph pipeline dynamically checks an `ACTIVE_LLM` environment variable. If the primary engine fails or is rate-limited, LangChain seamlessly pipes the exact same prompt configuration into OpenRouter's API, utilizing Meta's `Llama-3.3-70B-Instruct` as a zero-cost, high-IQ fallback. 

### Challenge 3: Google Sheets API Quota Exhaustion
**The Problem:** Writing to Google Sheets on every single job match quickly exhausted the Google Cloud API write quotas, crashing the CRM.
**The Solution:** I implemented "Shift-Left Deduplication" and bulk-insertion. The orchestrator downloads the entire sheet into a memory grid *once* at the start of the run. It deduplicates jobs via MD5 hashing (`platform_title_url`) in memory. Finally, it uses a safety valve to ensure it only performs a single `append_rows()` bulk API call, capped at 30 jobs per day.

### Challenge 4: Open-Source LLM JSON Parsing
**The Problem:** While OpenAI models return strict JSON, open-source models (like Llama 3) often wrap their JSON in Markdown (e.g., ` ```json `) or include conversational filler, breaking the Python `json.loads()` parser.
**The Solution:** I wrote a custom, robust JSON extractor that strips Markdown ticks and uses string manipulation (`str.find('{')`) to isolate and parse the JSON dictionary, ensuring the LangGraph pipeline never halts due to a hallucinated string.
