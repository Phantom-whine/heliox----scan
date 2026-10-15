#!/usr/bin/env python3
"""
HELIOX — Unified SaaS Terminal & Engine Launcher
Starts the Django Web Application, API, and background services.
"""

import os
import sys
import subprocess
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DJANGO_DIR = os.path.join(BASE_DIR, "corona-heliox-main")
TG_DIR = os.path.join(BASE_DIR, "heliox-tg-main")
SOLANA_SCANNER_DIR = os.path.join(BASE_DIR, "solana-scanner-main")


def run_web(host="127.0.0.1", port=8000):
    print(f"[*] Starting HELIOX Web Terminal at http://{host}:{port}/...")
    manage_py = os.path.join(DJANGO_DIR, "manage.py")
    cmd = [sys.executable, manage_py, "runserver", f"{host}:{port}"]
    subprocess.run(cmd, cwd=DJANGO_DIR)


def run_bot():
    print("[*] Starting HELIOX Telegram Bot...")
    bot_py = os.path.join(TG_DIR, "main.py")
    cmd = [sys.executable, bot_py]
    subprocess.run(cmd, cwd=TG_DIR)


def run_solana_scanner():
    print("[*] Starting Solana Mevx Scanner...")
    scanner_py = os.path.join(SOLANA_SCANNER_DIR, "main.py")
    cmd = [sys.executable, scanner_py]
    subprocess.run(cmd, cwd=SOLANA_SCANNER_DIR)


def run_bsc_scanner():
    print("[*] Starting BSC VAS Scanner...")
    bsc_py = os.path.join(DJANGO_DIR, "bsc-scan.py")
    cmd = [sys.executable, bsc_py]
    subprocess.run(cmd, cwd=DJANGO_DIR)


def run_migrations():
    print("[*] Running Database Migrations...")
    manage_py = os.path.join(DJANGO_DIR, "manage.py")
    subprocess.run([sys.executable, manage_py, "makemigrations"], cwd=DJANGO_DIR)
    subprocess.run([sys.executable, manage_py, "migrate"], cwd=DJANGO_DIR)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HELIOX Unified Runner")
    parser.add_argument("service", nargs="?", default="web", choices=["web", "bot", "solana", "bsc", "migrate"],
                        help="Service to launch (default: web)")
    parser.add_argument("--host", default="127.0.0.1", help="Host binding (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port binding (default: 8000)")

    args = parser.parse_args()

    if args.service == "web":
        run_web(args.host, args.port)
    elif args.service == "bot":
        run_bot()
    elif args.service == "solana":
        run_solana_scanner()
    elif args.service == "bsc":
        run_bsc_scanner()
    elif args.service == "migrate":
        run_migrations()
