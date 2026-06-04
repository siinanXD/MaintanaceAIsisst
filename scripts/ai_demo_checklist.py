#!/usr/bin/env python3
"""Run the AI demo question checklist against a running Maintenance Assistant app."""

from __future__ import annotations

import argparse
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
    (
        "Wie viele offene Aufgaben und wie viele offene Stoerungen haben wir?",
        {"task", "error"},
    ),
    ("Welche Mitarbeiter haben Dokumente hinterlegt?", {"employee"}),
    ("Welche Dokumente wurden bei Mitarbeitern hinterlegt?", {"employee_document"}),
)

EMPLOYEE_DOCUMENT_SESSION_FLOW = (
    ("Wie viele Mitarbeiter mit Dokumenten haben wir?", "employee_document_count"),
    ("Welche davon?", "employee_document_list"),
    ("welche", "employee_stored_document_list"),
)

STRUCTURED_EMPLOYEE_RESPONSE_TYPES = {
    "employee_document_list",
    "employee_stored_document_list",
    "employee_document_count",
    "employee_stored_document_count",
}

MULTI_SCOPE_RESPONSE_TYPES = {"multi_count"}


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


def chat(base_url, token, question, session_id=""):
    """Send one chat question and return the API payload."""
    body = {"message": question}
    if session_id:
        body["session_id"] = session_id
    return _request(
        "POST",
        f"{base_url}/api/v1/ai/chat",
        body,
        token=token,
    )


def response_type(result):
    """Return the normalized response type from one chat payload."""
    return str(
        result.get("response_type") or result.get("answer_category") or result.get("type") or ""
    ).strip()


def source_types(sources):
    """Return normalized source types from a chat response."""
    return {
        str(item.get("type") or item.get("source_type") or "").strip().lower()
        for item in (sources or [])
        if item
    }


def _expects_high_confidence(response_type):
    """Return whether a response type should expose high structured SQL confidence."""
    prefixes = (
        "employee_",
        "document_",
        "inventory_",
        "shiftplan_",
        "vacation_",
        "machine_",
        "tasks_",
    )
    return (
        response_type in STRUCTURED_EMPLOYEE_RESPONSE_TYPES
        or any(response_type.startswith(prefix) for prefix in prefixes)
        or response_type in {"structured_scope", "daily_briefing"}
    )


def evaluate_question(index, question, expected_types, result):
    """Evaluate one demo question and return a result row."""
    answer = str(result.get("answer") or result.get("message") or "").strip()
    sources = result.get("sources") or []
    found_types = source_types(sources)
    response = response_type(result)
    no_source = bool((result.get("answer_quality") or {}).get("no_answer")) or not sources
    overlap = found_types.intersection({item.lower() for item in expected_types})
    passed = bool(answer) and not no_source and bool(overlap)
    if not passed and response in STRUCTURED_EMPLOYEE_RESPONSE_TYPES:
        passed = bool(answer) and response in STRUCTURED_EMPLOYEE_RESPONSE_TYPES
    if not passed and "task" in expected_types and "error" in expected_types:
        passed = bool(answer) and response in MULTI_SCOPE_RESPONSE_TYPES
    confidence = result.get("confidence") or {}
    if passed and _expects_high_confidence(response):
        if confidence.get("level") not in (None, "", "high"):
            passed = False
    return {
        "index": index,
        "question": question,
        "passed": passed,
        "source_count": len(sources),
        "found_types": sorted(found_types),
        "expected_types": sorted(expected_types),
        "response_type": response,
        "confidence": confidence.get("score"),
        "confidence_level": confidence.get("level"),
        "answer_preview": answer[:140],
    }


def run_session_flow(base_url, token, flow_name):
    """Run one multi-turn session flow and return result rows."""
    if flow_name != "employee-documents":
        raise ValueError(f"unsupported_session_flow:{flow_name}")

    session_id = f"demo-checklist-{flow_name}"
    rows = []
    for step, (question, expected_type) in enumerate(EMPLOYEE_DOCUMENT_SESSION_FLOW, start=1):
        try:
            result = chat(base_url, token, question, session_id=session_id)
            actual_type = response_type(result)
            passed = actual_type == expected_type
            rows.append(
                {
                    "index": f"S{step}",
                    "question": question,
                    "passed": passed,
                    "source_count": len(result.get("sources") or []),
                    "found_types": [],
                    "expected_types": [expected_type],
                    "response_type": actual_type,
                    "confidence": (result.get("confidence") or {}).get("score"),
                    "confidence_level": (result.get("confidence") or {}).get("level"),
                    "answer_preview": str(result.get("answer") or "")[:140],
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "index": f"S{step}",
                    "question": question,
                    "passed": False,
                    "source_count": 0,
                    "found_types": [],
                    "expected_types": [expected_type],
                    "response_type": "error",
                    "confidence": None,
                    "confidence_level": None,
                    "answer_preview": str(exc)[:140],
                }
            )
    return rows


def print_report(rows, title):
    """Print a compact pass/fail report."""
    passed_count = sum(1 for row in rows if row["passed"])
    print(f"{title}: {passed_count}/{len(rows)} passed")
    print("-" * 88)
    for row in rows:
        status = "PASS" if row["passed"] else "FAIL"
        print(
            f"{status} #{row['index']} sources={row['source_count']} "
            f"type={row['response_type']} level={row.get('confidence_level') or '-'}"
        )
        print(f"      Q: {row['question']}")
        if not row["passed"]:
            print(
                f"      expected={','.join(row['expected_types'])} "
                f"preview={row['answer_preview']!r}"
            )
    print("-" * 88)
    return passed_count == len(rows)


def main():
    """Run the demo checklist and print a compact report."""
    parser = argparse.ArgumentParser(description="Run AI demo checklist against a live app.")
    parser.add_argument(
        "--session-flow",
        choices=("employee-documents",),
        help="Run an additional multi-turn session flow after single-turn questions.",
    )
    args = parser.parse_args()

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
                    "confidence_level": None,
                    "answer_preview": str(exc)[:140],
                }
            )

    all_passed = print_report(rows, "AI demo checklist")

    if args.session_flow:
        session_rows = run_session_flow(base_url, token, args.session_flow)
        session_passed = print_report(
            session_rows,
            f"AI demo session flow ({args.session_flow})",
        )
        all_passed = all_passed and session_passed

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
