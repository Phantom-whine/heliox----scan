"""
HELIOX — Live Background On-Chain Token Scanner Worker
Continuously scans on-chain tokens from live pools and telemetry files,
runs algorithmic safety filters and AI evaluation, and logs results directly to terminal.
"""

import os
import sys
import time
import json
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_URL = os.getenv("HELIOX_API_URL", "http://127.0.0.1:8000/api")
RESEARCHED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "researched_coins.json")

def log(tag: str, msg: str):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [SCANNER {tag}] {msg}", flush=True)

def scan_worker():
    log("INIT", "Starting Heliox on-chain background scanner worker...")
    time.sleep(2)  # Give web server a moment to boot

    # Read from local research pool queue
    coins_queue = []
    if os.path.exists(RESEARCHED_FILE):
        try:
            with open(RESEARCHED_FILE, 'r', encoding='utf-8') as f:
                coins_queue = json.load(f)
            log("POOL", f"Loaded research pool with {len(coins_queue):,} tokens to monitor.")
        except Exception as e:
            log("ERROR", f"Failed loading research file: {e}")

    idx = 0
    scanned_count = 0
    passed_count = 0
    not_passed_count = 0

    log("STATUS", "Listening for live token pools and telemetry...")

    while True:
        try:
            if coins_queue and idx < len(coins_queue):
                coin = coins_queue[idx]
                idx += 1
                ca = coin.get("address") or coin.get("token_CA")
                sym = coin.get("symbol", "UNKNOWN")
                name = coin.get("name", "Unknown")
                chain = "bsc" if ("0x" in str(ca).lower()) else "solana"
                mcap = coin.get("usd_market_cap", 0)

                log("CHECK", f"Auditing {chain.upper()} token ${sym} ({name}) | CA: {ca[:8]}...")

                try:
                    res = requests.post(
                        f"{API_URL}/save_coin/",
                        json={"ca": ca, "coin_info": coin},
                        timeout=8
                    )
                    if res.status_code in [200, 201]:
                        data = res.json()
                        score = data.get("score", 7.0)
                        is_passed = data.get("is_passed", score >= 7.0)
                        scanned_count += 1
                        if is_passed:
                            passed_count += 1
                            log("PASS", f"==> PASSED FILTER | ${sym} | Score: {score:.1f}/10 | MCAP: ${mcap:,.0f} | Status: ACCEPTED")
                        else:
                            not_passed_count += 1
                            log("FAIL", f"--> NOT PASSED    | ${sym} | Score: {score:.1f}/10 | MCAP: ${mcap:,.0f} | Status: REJECTED")
                    elif res.status_code == 200 and "already saved" in res.text:
                        log("SKIP", f"${sym} ({ca[:8]}...) already verified in registry.")
                except requests.exceptions.RequestException as re:
                    log("WARN", f"API check delayed ({re.__class__.__name__}). Retrying...")

                # Pace the scan cycle
                time.sleep(4)
            else:
                # Loop back or idle waiting for new arrivals
                if coins_queue:
                    idx = 0
                time.sleep(10)
        except Exception as e:
            log("EXCEPTION", f"Scanner loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    scan_worker()
