# Key-Scraper — GitHub Commit API Key Scraper

<p align="center">
  <img src="./cat.png" alt="Cat" width="400">
</p>


## 🧠 Context
Real-time GitHub commit scanner that watches the public events firehose and flags leaked API keys/tokens in recent commits. Built with FastAPI and httpx, with a live dashboard and simple JSON API.

**Keywords:** API key scraper, token scanner, secret leak detector, GitHub commit scanner, security research

---

## ⭐ Features

- Monitors GitHub’s public Events API (“firehose”) in near real time  
- ETag-aware polling to reduce bandwidth and avoid redundant work  
- Background async worker for continuous scanning  
- Live dashboard showing status, scanned diffs, and recent catches  
- JSON API for integrations and automation  
- Persists ETag/last poll time to survive restarts

---

## 🔧 How to Set Up

1. **Create a Hugging Face Account**  
   If you don’t already have one, sign up for a new account on Hugging Face.

2. **Create a New Space**  
   - Go to *Spaces*  
   - Click **Create New Space**  
   - Select **Docker** as the runtime  

3. **Download Project Files**  
   - Go to the GitHub repository  
   - Download all files from the `Files` folder  

4. **Upload Files to Hugging Face Space**  
   - Upload the downloaded files into your newly created Hugging Face Space  

5. **Add Your GitHub Token**  
   - Open `app.py`  
   - Locate line 14  
   - Replace `Enter_Github_Token` with your GitHub Personal Access Token (PAT)  

6. **Mount a Storage Bucket**  
   - Go to *Space Settings* → *Storage / Buckets*  
   - Create and mount a new bucket  
   - It will automatically load the default configuration, so you don’t need to change anything  

---

## ⚙️ How It Works

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

