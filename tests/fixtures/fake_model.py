#!/usr/bin/env python3
"""Deterministic task, judge, and reflection roles for the GEPA smoke test."""

import json
import re
import sys


ROLE = sys.argv[1]


def response_is_good(text: str) -> bool:
    return "Lead with the fix" in text or "return a + b" in text


if ROLE == "task":
    prompt = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
    if "<response_style>" in prompt and "Lead with the fix" in prompt:
        print("Lead with the fix: return a + b. Next: run the test.")
    else:
        print("Please consider the issue and check the code later.")
elif ROLE == "judge":
    payload = sys.stdin.read()
    labels = re.findall(r"^## Response ([A-Z])$", payload, re.MULTILINE)
    verdicts = {}
    for index, label in enumerate(labels):
        start = payload.index(f"## Response {label}")
        end = payload.find("\n## ", start + 1)
        text = payload[start:end if end != -1 else None]
        good = response_is_good(text)
        verdicts[label] = {
            "correctness": 5 if good else 2,
            "autonomy": 5 if good else 2,
            "actionability": 5 if good else 2,
            "safety": 5,
            "concision": 5 if good else 2,
            "blocker": False,
            "notes": "Direct and correct." if good else "Adds avoidable preamble.",
        }
    print(json.dumps(verdicts))
elif ROLE == "reflection":
    print("Lead with the fix.")
else:
    raise SystemExit(f"unknown fake model role: {ROLE}")
