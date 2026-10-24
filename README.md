# JRide Dispatcher: a Bedrock agent whose first decision is made by Strands Decider 2B

Riders message in plain English. **Decider 2B triages every message in ~100 ms, locally, before any LLM runs.**
Emergencies, off-topic chatter and prompt-injection are answered instantly with zero model tokens; real ride
requests reach a **Bedrock**-backed Strands agent tagged with how urgent they are. The agent then dispatches
cars through a from-scratch geohash matching engine (the Java **JRide** engine, vendored in `engine/`).

**Decision pattern: `#policy`** · Tags: `#strands-decider-2b` `#policy`

```
rider message
     │
     ▼
┌──────────────────────────────────────────────┐   7 categories, calibrated confidence
│ PolicyGate (Strands InterventionHandler)     │──────────────────────────────────────┐
│   Decider 2B: "which policy applies?"        │                                      │
└──────────────────────────────────────────────┘                                      │
  allow: urgent_ride · standard_ride · needs_details · cancel_or_status               │ block (needs conf ≥ 0.6)
     │  tagged "[policy: urgent_ride] ..."                                            ▼
     ▼                                                       emergency → "call 112"  (0 LLM calls)
Strands Agent on Amazon Bedrock (Nova Lite by default)       out_of_scope → polite redirect
  tools: find_place · request_ride · cancel_ride · zone_status      abuse_or_fraud → refuse
     │
     ▼
JRide Java engine (REST): geohash ring search → nearest driver, price-time fairness
```

## Why this decision belongs to a small model

A ride dispatcher gets a stream of messages where a few categories need *no* generation (a canned "call 112"
beats a generated paragraph, and must never be skipped or hallucinated) and the rest need the LLM to behave
differently (urgent: act now, no questions; vague: ask exactly one thing). That is a classification problem
that repeats on every message, which is exactly where a typed, calibrated, 2B-parameter decider is a better fit than
a frontier model: lower latency, no per-token cost, and a confidence number the code can threshold.

## Run it

Prereqs: Python 3.10+, JDK 21, and for the real thing a machine that can run the 2B model (CUDA GPU, Apple
silicon, or CPU) plus AWS credentials with Bedrock model access.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt strands-decider

# terminal 1: the dispatch engine (pure JDK, no Maven needed)
scripts/run_engine.sh --port 8080 --drivers 150

# terminal 2: the Decider (first run downloads the weights from Hugging Face)
scripts/run_decider.sh                      # DEVICE=cpu scripts/run_decider.sh to force CPU

# terminal 3: the agent (Bedrock; set a region/model you have access to)
export AWS_REGION=us-east-1
export JRIDE_MODEL_ID=us.amazon.nova-lite-v1:0     # any Bedrock model/inference profile that supports tools
python -m jride_agent --demo                # scripted walkthrough of every route
python -m jride_agent                       # or chat as a rider
```

No GPU or weights handy? `scripts/run_mock_decider.sh` starts a **keyword stand-in** with the same wire format so you can
see the wiring work. It is not the model and its accuracy means nothing.

## Measure it

```bash
python bench/bench.py --decider 127.0.0.1:8099 --llm --llm-model us.amazon.nova-lite-v1:0 \
    --price-in <USD/1M in> --price-out <USD/1M out>
```

`bench/dataset.jsonl` has 70 labelled messages (10 per category, including adversarial ones). The report gives
accuracy, **emergencies not caught**, **legitimate requests wrongly blocked**, p50/p95 latency, tokens and cost
per 1k decisions, for Decider 2B vs a Bedrock LLM doing the same classification. Results are written to
`bench/results.md`. The numbers there are yours; none are shipped in this repo.

## Tests

```bash
pip install -r requirements-dev.txt && python -m pytest -q
```

18 tests, including end-to-end runs through a real Strands `Agent` against the real Java engine (with a scripted model
and the keyword stand-in, so they need neither Bedrock nor weights). They check that blocked messages make **zero**
model calls, that a dispatched ride is actually `MATCHED` by the engine, that unknown places are never dispatched,
that riders can't cancel each other's requests, and that the Decider being down fails open to the LLM.

## Reusable asset

[`decision_patterns/policy_triage/`](decision_patterns/policy_triage): the typed question + option set, the
`InterventionHandler` wiring, and a how-to. Copy the folder, change the `PolicySpec`, done. `example.py` re-uses it
for a support desk in 25 lines.

## Layout

```
decision_patterns/policy_triage/   reusable Decider policy pattern (the asset)
jride_agent/                       the agent: policy, tools, places, Bedrock wiring, CLI
engine/                            JRide Java dispatch engine (REST), unchanged except --port/--drivers flags
bench/                             labelled dataset + Decider-vs-LLM benchmark
mock/                              keyword stand-in for the Decider (dev/test only)
tests/                             pytest suite
```

## Honest limits

- Decider 2B is experimental. The gate fails open and never blocks on a low-confidence guess for exactly that reason.
- The 7-way policy depends on your checkpoint's `num_slots`; the CLI checks `/health` at startup.
- Matching uses straight-line distance; the ETA is a labelled rough estimate, not live traffic (see `engine/ENGINE_README.md`).
- Place names resolve through a small built-in Dublin gazetteer, so the model can't invent coordinates.

MIT licensed (engine © Navya Mittal).
