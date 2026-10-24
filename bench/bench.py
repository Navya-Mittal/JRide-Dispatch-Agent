"""Benchmark: Decider 2B vs a Bedrock LLM on the same policy decision.

    # Decider only (needs `strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19 --port 8099`)
    python bench/bench.py --decider 127.0.0.1:8099

    # Decider vs Bedrock LLM (needs AWS credentials + model access)
    python bench/bench.py --decider 127.0.0.1:8099 --llm --llm-model us.amazon.nova-lite-v1:0 \
        --price-in 0.06 --price-out 0.24      # your model's USD per 1M tokens

Reports accuracy, per-category recall, the two numbers that matter for a *gate* (emergencies that got
through, legitimate requests that got blocked), latency percentiles, and the share of traffic the gate
resolves with zero LLM calls. Writes bench/results.json and bench/results.md.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from decision_patterns.policy_triage import DeciderClient, PolicyGate  # noqa: E402
from jride_agent.policy import CATEGORIES, SPEC  # noqa: E402

BLOCKING = {c for c, r in SPEC.routes.items() if r.action == "block"}
RIDEY = {"urgent_ride", "standard_ride", "needs_details", "cancel_or_status"}


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))] if xs else float("nan")


def run_decider(rows, host, warmup=3):
    gate = PolicyGate(SPEC, DeciderClient(host), fail_open=False)
    for r in rows[:warmup]:
        gate.decide(r["text"])
    out = []
    for r in rows:
        t0 = time.perf_counter()
        d = gate.decide(r["text"])
        wall = (time.perf_counter() - t0) * 1000
        out.append({**r, "pred": d.category, "action": d.action, "conf": d.confidence,
                    "server_ms": d.latency_ms, "wall_ms": wall, "in_tok": 0, "out_tok": 0})
    return out


LLM_PROMPT = (
    "You triage messages for JRide, a ride-hailing dispatcher in Dublin. Classify the message into exactly one "
    "category. Reply with ONLY the category name.\n\nCategories:\n"
    + "\n".join(f"- {k}: {v}" for k, v in CATEGORIES.items())
)


def run_llm(rows, model_id, region, warmup=1):
    import boto3

    client = boto3.client("bedrock-runtime", region_name=region)

    def call(text):
        t0 = time.perf_counter()
        res = client.converse(modelId=model_id, system=[{"text": LLM_PROMPT}],
                              messages=[{"role": "user", "content": [{"text": text}]}],
                              inferenceConfig={"maxTokens": 12, "temperature": 0})
        wall = (time.perf_counter() - t0) * 1000
        ans = "".join(b.get("text", "") for b in res["output"]["message"]["content"]).strip().lower()
        ans = ans.strip("`'\". ").split()[0] if ans else ""
        u = res.get("usage", {})
        return ans, wall, u.get("inputTokens", 0), u.get("outputTokens", 0)

    for r in rows[:warmup]:
        call(r["text"])
    out = []
    for r in rows:
        ans, wall, i, o = call(r["text"])
        pred = ans if ans in CATEGORIES else "invalid"
        out.append({**r, "pred": pred, "action": "block" if pred in BLOCKING else "allow", "conf": None,
                    "server_ms": wall, "wall_ms": wall, "in_tok": i, "out_tok": o})
    return out


def summarize(name, res, price_in=None, price_out=None):
    n = len(res)
    acc = sum(r["pred"] == r["label"] for r in res) / n
    by = defaultdict(lambda: [0, 0])
    for r in res:
        by[r["label"]][1] += 1
        by[r["label"]][0] += r["pred"] == r["label"]
    emerg = [r for r in res if r["label"] == "emergency"]
    emerg_through = sum(r["action"] != "block" or r["pred"] != "emergency" for r in emerg)
    # a legitimate ride message that the gate would block is the costly error
    legit = [r for r in res if r["label"] in RIDEY]
    false_block = sum(r["pred"] in BLOCKING for r in legit)
    blocked = sum(r["action"] == "block" for r in res)
    lat = [r["wall_ms"] for r in res]
    s = {
        "name": name, "n": n, "accuracy": acc,
        "recall": {k: v[0] / v[1] for k, v in by.items()},
        "emergencies_not_caught": f"{emerg_through}/{len(emerg)}",
        "legit_requests_blocked": f"{false_block}/{len(legit)}",
        "resolved_without_llm_pct": 100 * blocked / n,
        "p50_ms": pct(lat, 50), "p95_ms": pct(lat, 95), "mean_ms": statistics.fmean(lat),
        "in_tokens": sum(r["in_tok"] for r in res), "out_tokens": sum(r["out_tok"] for r in res),
        "confusion": Counter((r["label"], r["pred"]) for r in res if r["label"] != r["pred"]).most_common(12),
    }
    if price_in is not None and price_out is not None:
        s["usd_per_1k_decisions"] = 1000 * (s["in_tokens"] * price_in + s["out_tokens"] * price_out) / 1e6 / n
    return s


def markdown(summaries, note):
    L = ["# Benchmark results", "", note, "",
         "| | " + " | ".join(s["name"] for s in summaries) + " |", "|---|" + "---|" * len(summaries)]
    rows = [
        ("Accuracy (7-way)", lambda s: f"{s['accuracy']:.1%}"),
        ("Emergencies not caught", lambda s: s["emergencies_not_caught"]),
        ("Legit ride requests wrongly blocked", lambda s: s["legit_requests_blocked"]),
        ("p50 latency", lambda s: f"{s['p50_ms']:.0f} ms"),
        ("p95 latency", lambda s: f"{s['p95_ms']:.0f} ms"),
        ("Input / output tokens", lambda s: f"{s['in_tokens']} / {s['out_tokens']}"),
        ("USD per 1k decisions", lambda s: f"${s['usd_per_1k_decisions']:.4f}" if "usd_per_1k_decisions" in s else "n/a"),
    ]
    for label, f in rows:
        L.append(f"| {label} | " + " | ".join(f(s) for s in summaries) + " |")
    L += ["", "Per-category recall:", ""]
    cats = list(CATEGORIES)
    L += ["| category | " + " | ".join(s["name"] for s in summaries) + " |", "|---|" + "---|" * len(summaries)]
    for c in cats:
        L.append(f"| {c} | " + " | ".join(f"{s['recall'].get(c, 0):.0%}" for s in summaries) + " |")
    for s in summaries:
        L += ["", f"Top confusions ({s['name']}): " + (", ".join(f"{a}→{b} ×{n}" for (a, b), n in s["confusion"]) or "none")]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(ROOT / "bench" / "dataset.jsonl"))
    ap.add_argument("--decider", required=True, help="host:port of `strands-decider serve`")
    ap.add_argument("--llm", action="store_true", help="also run the Bedrock LLM baseline")
    ap.add_argument("--llm-model", default="us.amazon.nova-lite-v1:0")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--price-in", type=float, help="LLM USD per 1M input tokens")
    ap.add_argument("--price-out", type=float, help="LLM USD per 1M output tokens")
    ap.add_argument("--out", default=str(ROOT / "bench"))
    ap.add_argument("--note", default="")
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.dataset, encoding="utf-8") if l.strip()]
    summaries = [summarize("Decider 2B", run_decider(rows, a.decider))]
    if a.llm:
        summaries.append(summarize(f"LLM ({a.llm_model})", run_llm(rows, a.llm_model, a.region), a.price_in, a.price_out))
    note = a.note or f"{len(rows)} labelled messages, decider at {a.decider}."
    Path(a.out, "results.json").write_text(json.dumps(summaries, indent=2, default=str))
    md = markdown(summaries, note)
    Path(a.out, "results.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
