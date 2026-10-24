"""Policy triage: classify an incoming request with Strands Decider 2B *before* the LLM runs.

Drop-in pattern for the "Policy" decision category. You supply:

  1. a typed question + option set   -> ``PolicySpec(question=..., categories={...})``
  2. a route per option              -> ``Route("allow")`` or ``Route("block", reply="...")``

``PolicyGate`` is a Strands ``InterventionHandler`` that sits in front of the agent:

  * ``allow``  -> the request proceeds to the Bedrock-backed agent, tagged with its category
                  (``[policy: urgent_ride] ...``) so the system prompt can adapt behaviour.
  * ``block``  -> the agent is cancelled before any model call and the canned reply is
                  returned. Zero LLM tokens, one ~100 ms Decider call.
  * low confidence on a *block* route is never blocked: it falls through to the LLM
    (blocking a legitimate request is costlier than spending one LLM call).
  * Decider unreachable -> fail open to the LLM (configurable).

Only dependencies: ``strands-agents`` and the standard library. The Decider is called over
HTTP (``strands-decider serve <checkpoint> --port 8099``), so the model can live anywhere.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Literal

from strands.interventions import InterventionHandler, Proceed, Deny, Transform

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1:8099"


class DeciderError(RuntimeError):
    """The Decider server was unreachable or returned something unusable."""


class DeciderClient:
    """Minimal client for the Decider ``POST /v1/systemone`` endpoint."""

    def __init__(self, host: str | None = None, timeout: float = 30.0):
        host = host or os.environ.get("STRANDS_DECIDER_HOST", DEFAULT_HOST)
        if not host.startswith("http"):
            host = "http://" + host
        self.url = host.rstrip("/") + "/v1/systemone"
        self.timeout = timeout

    def ask(self, state: str, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        body = json.dumps({"state": state, "questions": questions}).encode()
        req = urllib.request.Request(self.url, data=body, headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                return json.loads(res.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise DeciderError(f"decider call failed: {exc}") from exc

    def health(self) -> dict[str, Any]:
        """GET /health: model name, device and ``num_slots`` (max options per question)."""
        try:
            with urllib.request.urlopen(self.url.rsplit("/v1/", 1)[0] + "/health", timeout=self.timeout) as res:
                return json.loads(res.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise DeciderError(f"decider health check failed: {exc}") from exc

    def choose(self, state: str, instructions: str, options: dict[str, str]) -> dict[str, Any]:
        """Pick one option. Returns choice, probabilities, confidence and latency_ms."""
        r = self.ask(state, {"q": {"type": "choice", "instructions": instructions, "criteria": options}})
        try:
            a = r["answers"]["q"]
            return {
                "choice": a["choice"],
                "probabilities": a["probabilities"],
                "confidence": float(a["confidence"]),
                "latency_ms": float(r.get("latency_ms", 0.0)),
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise DeciderError(f"unexpected decider response: {r!r}") from exc


@dataclass(frozen=True)
class Route:
    """What to do when the Decider picks a category."""

    action: Literal["allow", "block"] = "allow"
    reply: str | None = None  # canned reply, used when action == "block"


@dataclass(frozen=True)
class PolicySpec:
    """The reusable part: a typed question, its option set, and a route per option."""

    question: str
    categories: dict[str, str]  # option name -> description the Decider reads
    routes: dict[str, Route]
    context: str = ""  # static facts about your service, prepended to the state
    min_confidence: float = 0.0  # below this, treat the call as "unsure" and let the LLM handle it
    block_min_confidence: float = 0.6  # a block needs at least this much confidence

    def __post_init__(self) -> None:
        missing = set(self.categories) - set(self.routes)
        if missing:
            raise ValueError(f"no route for categories: {sorted(missing)}")


@dataclass
class Decision:
    """One recorded triage decision (kept on ``PolicyGate.log`` for UIs and benchmarks)."""

    text: str
    category: str
    confidence: float
    latency_ms: float
    action: str  # "allow" | "block" | "fallback"
    note: str = ""
    probabilities: dict[str, float] = field(default_factory=dict)


DENIED_PREFIX = "DENIED: "


def clean_reply(text: str) -> str:
    """Strands prefixes a cancelled invocation's message with 'DENIED: '. Strip it for display."""
    return text[len(DENIED_PREFIX):] if text.startswith(DENIED_PREFIX) else text


def _last_user_text(messages: list[dict[str, Any]] | None) -> str:
    for m in reversed(messages or []):
        if m.get("role") == "user":
            parts = [b["text"] for b in m.get("content", []) if isinstance(b, dict) and "text" in b]
            if parts:
                return "\n".join(parts)
    return ""


class PolicyGate(InterventionHandler):
    """Strands intervention handler that triages each new request with Decider 2B."""

    name = "decider-policy-gate"

    def __init__(
        self,
        spec: PolicySpec,
        client: DeciderClient | None = None,
        fail_open: bool = True,
        tag_requests: bool = True,
    ):
        self.spec = spec
        self.client = client or DeciderClient()
        self.fail_open = fail_open
        self.tag_requests = tag_requests
        self.log: list[Decision] = []
        self.last: Decision | None = None

    def _state(self, text: str) -> str:
        header = f"--- SERVICE ---\n{self.spec.context}\n\n" if self.spec.context else ""
        return f"{header}--- INCOMING MESSAGE ---\n{text}"

    def decide(self, text: str) -> Decision:
        """Classify one message. Pure function of the text; used by the handler and the benchmark."""
        spec = self.spec
        try:
            r = self.client.choose(self._state(text), spec.question, spec.categories)
        except DeciderError as exc:
            if not self.fail_open:
                raise
            logger.warning("decider unavailable, failing open to the LLM: %s", exc)
            return Decision(text, "unknown", 0.0, 0.0, "fallback", note=str(exc))

        category, conf = r["choice"], r["confidence"]
        route = spec.routes.get(category, Route("allow"))
        if conf < spec.min_confidence:
            return Decision(text, category, conf, r["latency_ms"], "fallback", "low confidence", r["probabilities"])
        if route.action == "block" and conf < spec.block_min_confidence:
            return Decision(text, category, conf, r["latency_ms"], "fallback",
                            "block needs higher confidence; deferring to the LLM", r["probabilities"])
        return Decision(text, category, conf, r["latency_ms"], route.action, probabilities=r["probabilities"])

    # --- Strands lifecycle hook -------------------------------------------------
    def before_invocation(self, event, **kwargs):
        text = _last_user_text(event.messages)
        if not text:
            return Proceed()
        d = self.decide(text)
        self.log.append(d)
        self.last = d
        logger.info("policy=%s conf=%.2f latency=%.0fms action=%s", d.category, d.confidence, d.latency_ms, d.action)

        if d.action == "block":
            # Strands drops the user turn when an invocation is cancelled, which would leave the history
            # starting with an assistant message (Bedrock Converse rejects that on the next turn).
            # Record the user turn ourselves so the conversation keeps alternating user/assistant.
            event.agent.messages.extend(event.messages or [])
            return Deny(reason=self.spec.routes[d.category].reply or "This request can't be handled here.")

        if self.tag_requests:
            tag = f"[policy: {d.category if d.action == 'allow' else 'unsure'}] "

            def _apply(ev, _tag=tag):
                for m in reversed(ev.messages or []):
                    if m.get("role") == "user":
                        for b in m.get("content", []):
                            if isinstance(b, dict) and "text" in b:
                                b["text"] = _tag + b["text"]
                                return

            return Transform(apply=_apply, reason=f"tagged as {d.category}")
        return Proceed(reason=d.category)
