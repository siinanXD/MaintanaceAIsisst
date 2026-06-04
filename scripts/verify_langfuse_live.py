#!/usr/bin/env python3
"""Verify the running Flask server exposes Langfuse eval after restart."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

BASE_URL = os.getenv("LANGFUSE_SMOKE_BASE_URL", "http://127.0.0.1:5050").rstrip("/")
LOGIN = os.getenv("LANGFUSE_SMOKE_LOGIN", os.getenv("ADMIN_USERNAME") or "admin")
PASSWORD = os.getenv("LANGFUSE_SMOKE_PASSWORD", os.getenv("ADMIN_PASSWORD") or "Demo1234!")


def main():
    """Check health, AI status, and one traced chat on the live server."""
    ready = requests.get(f"{BASE_URL}/health/ready", timeout=10)
    if ready.status_code != 200:
        print(f"FAIL: /health/ready returned {ready.status_code}")
        return 1
    print("OK: /health/ready")

    login = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"login": LOGIN, "password": PASSWORD},
        timeout=15,
    )
    if login.status_code != 200:
        print(f"FAIL: login returned {login.status_code} (set LANGFUSE_SMOKE_LOGIN/PASSWORD)")
        return 1
    token = login.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    status = requests.get(f"{BASE_URL}/api/v1/ai/status", headers=headers, timeout=15)
    if status.status_code != 200:
        print(f"FAIL: /api/v1/ai/status returned {status.status_code}")
        return 1
    status_body = status.json()
    langfuse = status_body.get("langfuse") or status_body.get("data", {}).get("langfuse", {})
    print("Langfuse from live AI status:", json.dumps(langfuse, indent=2))
    if not langfuse.get("ready"):
        print("FAIL: Langfuse not ready on running server.")
        return 1

    chat = requests.post(
        f"{BASE_URL}/api/v1/ai/chat",
        headers=headers,
        json={
            "message": "Welche offenen Wartungsaufgaben gibt es heute?",
            "session_id": "langfuse-live-verify",
        },
        timeout=120,
    )
    if chat.status_code != 200:
        print(f"FAIL: chat returned {chat.status_code}")
        return 1

    chat_body = chat.json()
    diagnostics = chat_body.get("diagnostics") or {}
    trace_id = diagnostics.get("langfuse_trace_id") or ""
    print("chat_message_id:", chat_body.get("chat_message_id"))
    print("langfuse_trace_id:", trace_id or "(missing)")
    print("langfuse_enabled:", diagnostics.get("langfuse_enabled"))
    if not trace_id:
        print("FAIL: Live chat did not return langfuse_trace_id.")
        return 1

    print("OK: Live server Langfuse verification passed.")
    print("Check scores in Langfuse UI for trace:", trace_id)
    return 0


if __name__ == "__main__":
    time.sleep(1)
    raise SystemExit(main())
