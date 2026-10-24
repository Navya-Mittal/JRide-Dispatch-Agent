"""A scripted Strands model for tests: replays tool calls / text so no Bedrock is needed."""

from __future__ import annotations

import json
from typing import Any

from strands.models import Model


class ScriptedModel(Model):
    """Each ``stream`` call plays the next scripted step: ("tool", name, input) or ("text", str)."""

    def __init__(self, steps: list[tuple]):
        self.steps = list(steps)
        self.calls = 0
        self.seen_user_texts: list[str] = []

    def update_config(self, **kw: Any) -> None: ...
    def get_config(self) -> Any:
        return {}

    async def structured_output(self, output_model, prompt, system_prompt=None, **kw):  # pragma: no cover
        raise NotImplementedError
        yield

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kw):
        self.calls += 1
        for m in messages:
            if m["role"] == "user":
                for b in m["content"]:
                    if "text" in b:
                        self.seen_user_texts.append(b["text"])
        step = self.steps.pop(0) if self.steps else ("text", "(script exhausted)")
        yield {"messageStart": {"role": "assistant"}}
        if step[0] == "tool":
            _, name, inp = step
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": f"t{self.calls}", "name": name}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(inp)}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": step[1]}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
        yield {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                            "metrics": {"latencyMs": 1}}}
