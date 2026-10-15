#!/usr/bin/env python3
"""
HELIOX — Unified Services Supervisor
Orchestrates and manages the Heliox Web API, Telegram Bot, and Scanner Workers.
Handles graceful shutdown of all spawned processes on exit.
"""

import os
import sys
import time
import signal
import subprocess
import threading
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DJANGO_DIR = os.path.join(BASE_DIR, "corona-heliox-main")
TG_DIR = os.path.join(BASE_DIR, "heliox-tg-main")
SOLANA_DIR = os.path.join(BASE_DIR, "solana-scanner-main")

# Global list of running child processes
processes = []
shutting_down = False


def log(service: str, message: str):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [{service.upper():<10}] {message}")


def stream_output(process, name):
    """Streams stdout/stderr from a child process to console with service prefix."""
    try:
        for line in iter(process.stdout.readline, ''):
            if shutting_down:
                break
            line_str = line.strip()
            if line_str:
                log(name, line_str)
    except (ValueError, OSError):
        pass


def start_process(name, cmd, cwd, env=None):
    """Spawns a child process and attaches an output streaming thread."""
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    
    # Force unbuffered Python output
    proc_env["PYTHONUNBUFFERED"] = "1"
    proc_env["HELIOX_API_URL"] = "http://127.0.0.1:8000/api"

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=proc_env
        )
        processes.append((name, proc))
        t = threading.Thread(target=stream_output, args=(proc, name), daemon=True)
        t.start()
        log(name, f"Process started (PID: {proc.pid})")
        return proc
    except Exception as e:
        log(name, f"Failed to start: {e}")
        return None


def terminate_all():
    """Gracefully terminates all child processes."""
    global shutting_down
    if shutting_down:
        return
    shutting_down = True
    print("\n[!] Shutting down all Heliox services...")

    for name, proc in processes:
        if proc.poll() is None:
            log(name, f"Stopping process (PID: {proc.pid})...")
            try:
                if sys.platform == "win32":
                    subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], 
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    proc.terminate()
            except Exception:
                pass

    print("[*] All services stopped cleanly.")


def signal_handler(sig, frame):
    terminate_all()
    sys.exit(0)


def run_preflight_checks():
    """Runs database migrations before starting servers."""
    log("SYSTEM", "Running preflight database migration check...")
    manage_py = os.path.join(DJANGO_DIR, "manage.py")
    res = subprocess.run([sys.executable, manage_py, "migrate", "--noinput"], 
                         cwd=DJANGO_DIR, capture_output=True, text=True)
    if res.returncode == 0:
        log("SYSTEM", "Database schema is up to date.")
    else:
        log("SYSTEM", f"Migration warning: {res.stderr.strip()[:100]}")


def main():
    parser = argparse.ArgumentParser(description="HELIOX SaaS Services Supervisor")
    parser.add_argument("--host", default="127.0.0.1", help="Host binding for Web API (default: 127.0.0.1)")
    parser.add_argument("--port", default=8000, type=int, help="Port binding for Web API (default: 8000)")
    parser.add_argument("--no-bot", action="store_true", help="Do not start Telegram bot")
    parser.add_argument("--with-solana", action="store_true", help="Also start Mevx Solana background scanner")
    parser.add_argument("--with-bsc", action="store_true", help="Also start BSC VAS background scanner")

    args = parser.parse_args()

    # Register termination signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("=" * 65)
    print(" HELIOX — SaaS Terminal & Services Supervisor")
    print(f" Web & REST API: http://{args.host}:{args.port}/")
    print("=" * 65)

    run_preflight_checks()

    # 1. Start Django Web & REST API
    manage_py = os.path.join(DJANGO_DIR, "manage.py")
    api_cmd = [sys.executable, manage_py, "runserver", f"{args.host}:{args.port}"]
    start_process("WEB_API", api_cmd, DJANGO_DIR)

    # Allow server to bind
    time.sleep(1.5)

    # 2. Start Live On-Chain Scanner Worker
    scanner_worker_py = os.path.join(DJANGO_DIR, "scanner_worker.py")
    if os.path.exists(scanner_worker_py):
        start_process("SCANNER", [sys.executable, scanner_worker_py], DJANGO_DIR)

    # 3. Start Telegram Bot
    if not args.no_bot:
        tg_py = os.path.join(TG_DIR, "main.py")
        if os.path.exists(tg_py):
            start_process("TG_BOT", [sys.executable, tg_py], TG_DIR)
        else:
            log("TG_BOT", "Telegram bot script not found.")

    # 4. Optional: Solana Playwright Scanner
    if args.with_solana:
        solana_py = os.path.join(SOLANA_DIR, "main.py")
        if os.path.exists(solana_py):
            start_process("SOL_PLAYWRIGHT", [sys.executable, solana_py], SOLANA_DIR)
        else:
            log("SOL_PLAYWRIGHT", "Solana scanner script not found.")

    # 5. Optional: BSC Playwright Scanner
    if args.with_bsc:
        bsc_py = os.path.join(DJANGO_DIR, "bsc-scan.py")
        if os.path.exists(bsc_py):
            start_process("BSC_PLAYWRIGHT", [sys.executable, bsc_py], DJANGO_DIR)
        else:
            log("BSC_PLAYWRIGHT", "BSC scanner script not found.")

    print("\n[+] All requested services are running. Press Ctrl+C to terminate.")

    # Monitor processes loop
    try:
        while not shutting_down:
            time.sleep(1)
            # Check if web server exited unexpectedly
            for name, proc in processes:
                code = proc.poll()
                if code is not None and not shutting_down:
                    log(name, f"Process exited with code {code}")
    except KeyboardInterrupt:
        pass
    finally:
        terminate_all()


if __name__ == "__main__":
    main()
