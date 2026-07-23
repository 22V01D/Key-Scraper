<p align="center">
  <img src="./cat.png" alt="Tactical Cat" width="175">
</p>

<h1 align="center">Key-Scraper</h1>

<p align="center">
  Real-time GitHub commit scanner that detects leaked API keys and secrets.
</p>
> **IMPORTANT NOTE:**
> This project is made with the assistance of artificial intelligence.

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

#### B. Customize Scan Targets in `scanner.py`

Open `scanner.py` to customize what keys you want to scan for inside the `TARGET_MATRIX` dictionary.

> **IMPORTANT RECOMMENDATION:**
> It is **strongly advised to comment out or remove** `GEMINI_GOOGLE_AI`, `GOOGLE_OAUTH`, and `HEROKU_API` from `TARGET_MATRIX`. These patterns produce **tons of false positives** due to common regex matches on generic UUIDs, random hashes, and example parameters in public code.

To disable a scanner, put a `#` in front of its line or delete it:

```python
    # "GEMINI_GOOGLE_AI": re.compile(r"AIza[0-9A-Za-z-_]{35}"),  <-- Disabled (High false positives)
    # "GOOGLE_OAUTH": re.compile(r"ya29\.[a-zA-Z0-9_-]+"),        <-- Disabled (High false positives)
    # "HEROKU_API": re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}..."), <-- Disabled (High false positives)
```

##### List of Available Scan Options in `scanner.py`:

| Category | Available Target Key |
| --- | --- |
| **AI & LLMs** | `OPENAI_SK`, `OPENAI_PROJ`, `DEEPSEEK_SK`, `ANTHROPIC_SK`, `GROQ_API`, `OPENROUTER_SK`, `XAI_Grok_API`, `PERPLEXITY_API`, `FIREWORKS_API`, `ELEVENLABS_API`, `RUNWAY_API`, `DEEPAI_API` |
| **Cloud Platforms** | `AWS_AKIA`, `GCP_SERVICE_ACCOUNT`, `AZURE_PAT`, `IBM_WATSON_API`, `HUGGINGFACE_TOKEN` |
| **Google Services** *(High False-Positives)* | `GEMINI_GOOGLE_AI`, `GOOGLE_OAUTH` |
| **Database & Mail** | `DB_CONNECTION`, `SMTP_URL`, `MAIL_CONFIG_PASS`, `SENDGRID_API` |
| **Communication & Media** | `TWILIO_AUTH`, `IMAGGA_API` |
| **Crypto & Finance** | `BITCOIN_PRIV`, `ETH_PRIVATE`, `STRIPE_LIVE` |
| **Developer Tools** | `GITHUB_PAT`, `HEROKU_API` *(High False-Positives)*, `RSA_PRIVATE` |

> **Note:** A dedicated **automatic key validator module** for `scanner.py` is currently being built to filter, verify, and purge dead/false-positive keys automatically.

---

## ⚙️ How It Works

### 1. Firehose Poller
- A background task (`firehose_metronome`) hits  
  `https://api.github.com/events` every ~0.82s using httpx with HTTP/2 and connection pooling.  
- At this interval, the scanner makes **~73 requests per minute** (approximately **4,390 requests per hour**).
- Uses the response ETag and `If-None-Match` to avoid reprocessing unchanged pages (304 support).  
- With a GitHub Personal Access Token (PAT), your rate limit is **5,000 requests/hour**, which supports this continuous polling rate while leaving a small buffer for downloading the actual commit diffs. Without a token, you are severely limited to ~60 requests/hour and the scanner will constantly pause.
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

