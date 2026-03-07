# Changelog

All notable changes to the HustleBot project will be documented in this file.

## [v1.2.0] - 2026-03-07
### Added
- Implemented **Hybrid AI Router** allowing seamless failover between Google Gemini and OpenRouter (Llama 3.3 70B).
- Added `ARCHITECTURE.md` with comprehensive Mermaid user flow diagrams.
- Added strict timezone and location penalty prompting to filter out "fake remote" jobs.

### Fixed
- Resolved Playwright `TimeoutError` crashes on Y Combinator scraper by implementing soft-fail text extraction.
- Fixed JSON parsing crashes from open-source LLMs by implementing robust string-stripping logic.

## [v1.1.0] - 2026-03-01
### Added
- Migrated core orchestration to LangGraph for DAG state management.
- Added Google Sheets CRM integration with shift-left deduplication.
- Configured 96-minute GitHub Actions Cron Scheduler to bypass platform rate limits.

## [v1.0.0] - 2026-02-15
### Added
- Initial release.
- Basic API integrations for RemoteOK and LinkedIn Guest mode.
- Telegram HTML notification formatting.
