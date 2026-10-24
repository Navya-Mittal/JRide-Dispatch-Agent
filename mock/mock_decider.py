"""DEV/CI STAND-IN for `strands-decider serve`. It is a keyword matcher, NOT the model.

It speaks the same wire format (POST /v1/systemone, GET /health) so the whole stack can be developed and
tested without downloading weights or having a GPU. Never use its numbers as Decider results.

    python mock/mock_decider.py --port 8099
"""

from __future__ import annotations

import argparse
import re
import time
from typing import Any

from fastapi import FastAPI
import uvicorn

app = FastAPI(title="mock decider (stand-in)")

KEYWORDS: list[tuple[str, re.Pattern[str]]] = [
    ("emergency", re.compile(r"chest pain|heart attack|bleeding|on fire|\bfire\b|unconscious|stabbed|being attacked|"
                             r"can'?t breathe|overdos|someone is hurt|broke(n)? (his|her|my) |ambulance", re.I)),
    ("abuse_or_fraud", re.compile(r"ignore (all |your )?(previous|prior|above)|system prompt|you are now|"
                                  r"free ride|refund me|fake (request|ride)|stupid bot|f+u+c+k|shut up|"
                                  r"pretend (you|to)|jailbreak|developer mode", re.I)),
    ("cancel_or_status", re.compile(r"cancel|status of|any drivers|drivers available|how many drivers|"
                                    r"where is my (car|driver)|my (open )?requests?", re.I)),
    ("urgent_ride", re.compile(r"flight|train in|late for|asap|right now|hurry|emergency ride|urgent|"
                               r"missed my|boarding|in \d+ (min|minutes)|scared|unsafe|followed", re.I)),
    ("standard_ride", re.compile(r"\bfrom\b.+\b(to|until)\b|pick me up (at|from|near).+\b(to|for)\b|"
                                 r"ride (from|to).+\bto\b|take me (from|to)", re.I)),
    ("out_of_scope", re.compile(r"capital of|weather|joke|recipe|python|javascript|bitcoin|pizza|order food|"
                                r"hotel|flight (ticket|booking)|who (is|was)|poem|translate|homework", re.I)),
    ("needs_details", re.compile(r"\b(need|want|get|book|order|call)\b.*\b(ride|car|taxi|cab|lift)\b|"
                                 r"pick me up|take me|taxi", re.I)),
]


def classify(options: list[str], text: str) -> tuple[str, dict[str, float], float]:
    pick = next((name for name, rx in KEYWORDS if name in options and rx.search(text)), None)
    if pick is None:
        pick = "out_of_scope" if "out_of_scope" in options else options[0]
        top = 0.55
    else:
        top = 0.88
    rest = (1 - top) / max(1, len(options) - 1)
    probs = {o: (top if o == pick else rest) for o in options}
    return pick, probs, top


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "model": "MOCK-STAND-IN", "device": "none"}


@app.post("/v1/systemone")
def systemone(body: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    state = body.get("state", "")
    msg = state.split("--- INCOMING MESSAGE ---", 1)[-1] if isinstance(state, str) else str(state)
    answers: dict[str, Any] = {}
    for name, q in body["questions"].items():
        if q["type"] == "choice":
            options = list(q["criteria"])
            pick, probs, conf = classify(options, msg)
            answers[name] = {"type": "choice", "choice": pick, "probabilities": probs, "confidence": conf}
        elif q["type"] == "noul":
            answers[name] = {"type": "noul", "noul": 0.5}
        else:
            levels = q["criteria"]
            answers[name] = {"type": "score", "score": 0.0, "legend": {str(i): l for i, l in enumerate(levels)},
                             "probabilities": {str(i): 1 / len(levels) for i in range(len(levels))}, "confidence": 0.0}
    return {"model": "MOCK-STAND-IN", "answers": answers, "usage": {"input_tokens": 0, "output_tokens": 0},
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")
