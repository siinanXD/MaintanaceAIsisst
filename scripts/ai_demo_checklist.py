#!/usr/bin/env python3
"""Run the AI demo question checklist against a running Maintenance Assistant app."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5050")
DEFAULT_LOGIN = os.getenv("DEMO_LOGIN", "admin")
DEFAULT_PASSWORD = os.getenv("DEMO_PASSWORD", "Demo1234!")

DEMO_QUESTIONS = (
    ("Welche dringenden Aufgaben sind heute offen?", {"task"}),
    ("Welche Aufgabe ist an Hydraulikpresse 03 gerade dringend?", {"task", "machine"}),
    ("Was bedeutet Fehler INS-E-103?", {"error"}),
    ("Welche Loesung gibt es fuer Druck faellt ab an Hydraulikpresse 03?", {"error", "machine"}),
    ("Welche Materialien sind bei Hydraulikpresse 03 unter Mindestbestand?", {"inventory"}),
    ("Welche Wartungsaufgaben sind diese Woche faellig?", {"task"}),
    ("Welche Maschine hat aktuell offene oder laufende dringende Aufgaben?", {"task", "machine"}),
    ("Was ist bei Not-Halt-Kreis offen zu pruefen?", {"error"}),
    ("Welche Wartungsplaene sind an Hydraulikpresse 03 relevant?", {"maintenance_plan", "machine"}),
    (
        "Was steht im Manual zur Hydraulikpresse 03 bei Druckverlust?",
        {"machine_manual", "knowledge", "document"},
    ),
    ("Was wurde in der letzten Schicht zu Spritzgussanlage 04 gemeldet?", {"shift_handover"}),
    (
        "Welche Ersatzteile blockieren Wartung an Hydraulikpresse 03?",
        {"inventory", "manual_training"},
    ),
)


def _request(method, url, payload=None, token=None):
    """Perform an HTTP request and return parsed JSON."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def login(base_url, login_name, password):
    """Authenticate and return a bearer token."""
    payload = _request(
        "POST",
        f"{base_url}/api/v1/auth/login",
        {"login": login_name, "password": password},
    )
    token = payload.get("access_token") or payload.get("token")
    if not token and isinstance(payload.get("data"), dict):
        token = payload["data"].get("access_token") or payload["data"].get("token")
    if not token:
        raise RuntimeError("login_failed_no_token")
    return token


def chat(base_url, token, question):
    """Send one chat question and return the API payload."""
    return _request(
        "POST",
        f"{base_url}/api/v1/ai/chat",
        {"message": question},
        token=token,
    )


def source_types(sources):
    """Return normalized source types from a chat response."""
    return {
        str(item.get("type") or item.get("source_type") or "").strip().lower()
        for item in (sources or [])
        if item
    }


def evaluate_question(index, question, expected_types, result):
    """Evaluate one demo question and return a result row."""
    answer = str(result.get("answer") or result.get("message") or "").strip()
    sources = result.get("sources") or []
    found_types = source_types(sources)
    no_source = bool((result.get("answer_quality") or {}).get("no_answer")) or not sources
    overlap = found_types.intersection({item.lower() for item in expected_types})
    passed = bool(answer) and not no_source and bool(overlap)
    return {
        "index": index,
        "question": question,
        "passed": passed,
        "source_count": len(sources),
        "found_types": sorted(found_types),
        "expected_types": sorted(expected_types),
        "response_type": (
            result.get("response_type")
            or result.get("answer_category")
            or result.get("type")
            or ""
        ),
        "confidence": (result.get("confidence") or {}).get("score"),
        "answer_preview": answer[:140],
    }


def main():
    """Run the demo checklist and print a compact report."""
    base_url = DEFAULT_BASE_URL.rstrip("/")
    try:
        token = login(base_url, DEFAULT_LOGIN, DEFAULT_PASSWORD)
    except urllib.error.HTTPError as exc:
        print(f"LOGIN FAILED: HTTP {exc.code}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"LOGIN FAILED: {exc}", file=sys.stderr)
        sys.exit(1)

    rows = []
    for index, (question, expected_types) in enumerate(DEMO_QUESTIONS, start=1):
        try:
            result = chat(base_url, token, question)
            rows.append(evaluate_question(index, question, expected_types, result))
        except Exception as exc:
            rows.append(
                {
                    "index": index,
                    "question": question,
                    "passed": False,
                    "source_count": 0,
                    "found_types": [],
                    "expected_types": sorted(expected_types),
                    "response_type": "error",
                    "confidence": None,
                    "answer_preview": str(exc)[:140],
                }
            )

    passed_count = sum(1 for row in rows if row["passed"])
    print(f"AI demo checklist: {passed_count}/{len(rows)} passed")
    print("-" * 88)
    for row in rows:
        status = "PASS" if row["passed"] else "FAIL"
        print(
            f"{status} #{row['index']:02d} sources={row['source_count']} "
            f"type={row['response_type']} found={','.join(row['found_types']) or '-'}"
        )
        print(f"      Q: {row['question']}")
        if not row["passed"]:
            print(
                f"      expected={','.join(row['expected_types'])} "
                f"preview={row['answer_preview']!r}"
            )
    print("-" * 88)
    sys.exit(0 if passed_count == len(rows) else 1)


if __name__ == "__main__":
    main()
