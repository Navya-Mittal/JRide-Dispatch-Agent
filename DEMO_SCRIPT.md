# Demo video script (target 2:30, hard limit 3:00)

Record the terminal full-screen, font large. Three panes or just one with `--demo`. Public upload (YouTube unlisted is not "public": use Public).

**0:00–0:20 · Hook (talk over the architecture diagram from the README)**
"Most agents spend a frontier-model call on every message, even when the right answer is a fixed sentence. This is JRide, a Dublin ride dispatcher on Amazon Bedrock. Before the LLM sees anything, Strands Decider 2B makes one decision: which policy applies to this message."

**0:20–0:50 · Show the decision (README table or `policy.py`)**
"One typed question, seven options. Four go to the Bedrock agent with a label that changes its behaviour. Three never reach the LLM: emergencies, off-topic, and prompt injection."

**0:50–1:50 · Live run: `python -m jride_agent --demo`** (pause on each Decider line)
1. Urgent flight message → point at `[Decider 2B] urgent_ride … ms → sent to the Bedrock agent`, then the instant, two-sentence dispatch with a real driver id and distance.
2. "I need a ride" → one clarifying question.
3. **Heart attack message** → `BLOCKED before the LLM: 0 model calls`, the 112 reply. "Fixed text, ~100 ms, nothing generated."
4. Prompt injection → blocked.
5. Close with the summary line: "N messages triaged, M resolved without a single LLM token."

**1:50–2:20 · Numbers (`bench/results.md`)**
Show the table: Decider vs LLM on latency, cost per 1k decisions, and the two safety rows (emergencies not caught, legit requests wrongly blocked). Say your real numbers, including any place Decider lost.

**2:20–2:45 · Reusable pattern**
Open `decision_patterns/policy_triage/example.py`: "Same gate, support desk, 25 lines. Swap the question, options and routes."

**2:45–3:00 · Close**
"Decider decides, Bedrock generates. Code and article linked below. Tags: strands-decider-2b, policy."

Checklist before recording: engine + real Decider (not the mock) + real Bedrock credentials running; run `--demo` once off-camera to warm the model; `AWS_REGION` and `JRIDE_MODEL_ID` set.
