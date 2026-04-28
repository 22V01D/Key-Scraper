# Key-Scraper — GitHub Commit API Key Scraper

## Context
Real-time GitHub commit scanner that watches the public events firehose and flags leaked API keys/tokens in recent commits. Built with FastAPI and httpx, with a live dashboard and simple JSON API.

**Keywords:** API key scraper, token scanner, secret leak detector, GitHub commit scanner, security research

---

## Features

- Monitors GitHub’s public Events API (“firehose”) in near real time  
- ETag-aware polling to reduce bandwidth and avoid redundant work  
- Background async worker for continuous scanning  
- Live dashboard showing status, scanned diffs, and recent catches  
- JSON API for integrations and automation  
- Persists ETag/last poll time to survive restarts  

---

## How It Works

### 1. Firehose Poller
- A background task (`firehose_metronome`) hits  
  `https://api.github.com/events` every ~0.82s using httpx with HTTP/2 and connection pooling.  
- Uses the response ETag and `If-None-Match` to avoid reprocessing unchanged pages (304 support).  
- With a personal token, you get higher rate limits. Without it, you’re limited to ~60 requests/hour.  

---

### 2. Event Processing
- When a `200 OK` page of events arrives, the app calls  
  `extract_and_scan_diffs(client, events)` to examine relevant events (typically PushEvents) and fetch their commit diffs.  

---

### 3. Secret Detection
- The scanner module matches diff lines against provider-specific patterns, such as:
  - OpenAI: `sk-...`  
  - Anthropic: `sk-ant-...`  
  - GitHub: `ghp_...`, `github_pat_...`  
  - AWS: `AKIA...`  
  - Google: `AIza...`  
  - Private key headers  

- Matches are recorded to in-memory structures for stats and recent hits.  

---

### 4. Live Reporting
- The FastAPI route `/api/data` streams:
  - **status**: connection/auth status  
  - **scanned**: total diffs scanned  
  - **caught**: total secrets flagged  
  - **recent**: rolling list of recent catches with type/repo/preview  
  - **scans**: currently processed repos  

- The root route `/` serves a lightweight dashboard that polls `/api/data` every second.
