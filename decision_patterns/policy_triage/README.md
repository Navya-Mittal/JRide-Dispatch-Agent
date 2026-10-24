# Decision pattern: Policy triage (`#policy`)

**Classify every incoming request into a category with Strands Decider 2B *before* the LLM runs, and route on the category.**

Some categories deserve a fast canned answer (emergency, spam, off-topic, prompt-injection). Others need the LLM, and
should reach it with a label that tells it how to behave. Decider 2B decides which, in about 100 ms, locally,
with a calibrated confidence you can threshold.

## The recipe

| Piece | Where | You change |
|---|---|---|
| Typed question + option set | `PolicySpec(question=..., categories={name: description})` | the question, the options and their descriptions |
| Route per option | `PolicySpec(routes={name: Route("allow") \| Route("block", reply=...)})` | what each category does |
| Wiring | `Agent(..., interventions=[PolicyGate(spec)])` | nothing |

`PolicyGate` is a Strands `InterventionHandler` (`before_invocation`):

- **allow**: the message continues to the agent, prefixed with `[policy: <category>] `. Reference the tags in your system prompt.
- **block**: the invocation is cancelled before any model call; the canned reply comes back. Zero LLM tokens.
- **Low confidence never blocks**: a block route needs `block_min_confidence` (default 0.6), else the message falls through to the LLM tagged `[policy: unsure]`.
- **Decider unreachable**: fails open to the LLM (`fail_open=False` raises instead).
- Every decision is kept on `gate.log` (category, confidence, latency, action) for dashboards and evals.

## Use it

```python
from decision_patterns.policy_triage import PolicyGate, PolicySpec, Route
gate = PolicyGate(PolicySpec(question="...", categories={...}, routes={...}))
agent = Agent(model=..., interventions=[gate])
```

Run `strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19 --port 8099` (or set `STRANDS_DECIDER_HOST`).
See `example.py` for a support-desk version and `jride_agent/policy.py` for a full 7-way policy.

## Tips learned the hard way

1. **Describe each option in one concrete sentence.** The Decider reads the descriptions; they are the prompt.
2. **Keep the option count within the checkpoint's `num_slots`** (`GET /health`). Merge categories if needed.
3. **Make the costly error hard.** Blocking a legitimate request is worse than spending one LLM call, so blocks need a higher confidence bar than allows.
4. **Strands drops the user turn when an invocation is cancelled.** `PolicyGate` re-adds it so history still starts with a user message (Bedrock Converse rejects histories that start with an assistant message).
5. **Tag, don't trust.** Rider text can contain `[policy: ...]` too. Say in the system prompt that the gate's tag is the trusted one, and add a Decider category for injection attempts (JRide does).
6. **Tune on your own data.** `bench/bench.py` shows the harness: accuracy, missed emergencies, wrongly blocked requests, latency vs an LLM baseline.
