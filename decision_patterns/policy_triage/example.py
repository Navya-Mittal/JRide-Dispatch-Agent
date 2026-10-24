"""Reuse the pattern in a different domain in ~25 lines: a support-desk agent.

    strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19 --port 8099 &
    python -m decision_patterns.policy_triage.example
"""

from strands import Agent

from decision_patterns.policy_triage import PolicyGate, PolicySpec, Route, clean_reply

spec = PolicySpec(
    question="Which handling policy applies to this support message?",
    context="Support desk for a SaaS billing product.",
    categories={
        "how_to": "asks how to use a feature",
        "billing_issue": "failed payment, refund, invoice problem",
        "outage": "reports the product being down or data loss",
        "spam": "marketing, scams or irrelevant content",
    },
    routes={
        "how_to": Route("allow"),
        "billing_issue": Route("allow"),
        "outage": Route("block", reply="Paging the on-call engineer now. Status: https://status.example.com"),
        "spam": Route("block", reply="Thanks, but this inbox is for support requests."),
    },
)

if __name__ == "__main__":
    gate = PolicyGate(spec)
    agent = Agent(system_prompt="You are a billing support assistant.", interventions=[gate])  # + your model/tools
    for msg in ["Everything is down and my data is gone!", "How do I download an invoice?"]:
        r = agent(msg)
        print(gate.last.category, gate.last.action, "|", clean_reply(r.message["content"][0]["text"])[:80])
