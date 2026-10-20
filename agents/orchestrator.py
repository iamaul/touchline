"""Orchestrator — coordinates the Touchline agent pipeline.

One shared MatchState; four specialist agents in a fixed handoff chain:

    engine -> interpreter (MomentDetector)
           -> moment-explainer (ExplainerAgent)
           -> narrator (NarratorAgent)
           -> personalizer (PersonalizerAgent, one packet per viewer profile)

Responsibilities (the multi-agent judging criteria):
  shared state      — MatchState owned here; agents read, orchestrator writes
  handoffs          — every agent→agent transition logged with payloads' shape
  failure recovery  — each stage retried with backoff; exhausted stages fall
                      back to a deterministic degraded-but-grounded result so
                      the live broadcast NEVER stalls (chaos_prob injects
                      failures deterministically to demonstrate recovery)
  agent trace       — machine-readable JSONL of every handoff for the UI
"""

from __future__ import annotations

import json
import random
import time
from typing import Callable, Optional

from agents import MatchState, StatsEngine
from agents.explainer import ExplainerAgent
from agents.llm import ChatConfig
from agents.moments import MomentDetector
from agents.narrator import NarratorAgent, OVERLAY_DURATION
from agents.personalizer import PersonalizerAgent, ViewerProfile

CHAIN = ["engine", "interpreter", "moment-explainer", "narrator", "personalizer"]

MAX_ATTEMPTS = 2
RETRY_BACKOFF_S = 0.06


class AgentTrace:
    """Append-only agent handoff log; one entry = one handoff attempt result."""

    def __init__(self):
        self.seq = 0
        self.entries: list[dict] = []

    def log(self, t: float, handoff: str, agent: str, action: str,
            status: str, attempt: int, detail: str = "") -> None:
        self.seq += 1
        self.entries.append({
            "seq": self.seq,
            "t": round(t, 1),
            "handoff": handoff,
            "agent": agent,
            "action": action,
            "status": status,          # ok | retry | error | fallback
            "attempt": attempt,
            "detail": detail,
        })

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(e, ensure_ascii=False) for e in self.entries)


class Orchestrator:
    def __init__(self, state: MatchState, profiles: list[ViewerProfile],
                 chat_cfg: Optional[ChatConfig] = None,
                 chaos_prob: float = 0.0, seed: int = 42):
        self.state = state
        self.engine = StatsEngine(state)
        self.detector = MomentDetector()
        self.explainer = ExplainerAgent()
        self.narrator = NarratorAgent(chat_cfg=chat_cfg)
        self.personalizer = PersonalizerAgent(chat_cfg=chat_cfg)
        self.profiles = profiles
        self.chaos_prob = chaos_prob
        self.rng = random.Random(seed)
        self.trace = AgentTrace()
        self.stats = {"moments": 0, "packets": 0, "retries": 0, "fallbacks": 0}

    # ------------------------------------------------------------ internals

    def _chaos_check(self) -> Optional[str]:
        if self.chaos_prob > 0 and self.rng.random() < self.chaos_prob:
            return "injected: simulated agent crash"
        return None

    def _run_stage(self, ev, from_agent: str, agent: str, action: str,
                   fn: Callable) -> Optional[object]:
        """Run one pipeline stage with retries + backoff.

        Returns the stage result, or None if every attempt failed.
        Success on attempt>1 is logged as 'ok' with attempt:2 — that IS the
        recovery story.
        """
        handoff = f"{from_agent} -> {agent}"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            fault = self._chaos_check()
            if fault:
                # injected failure models a real agent crash
                self.trace.log(ev.t, handoff, agent, action,
                               "retry" if attempt < MAX_ATTEMPTS else "error",
                               attempt, detail=fault)
                if attempt < MAX_ATTEMPTS:
                    self.stats["retries"] += 1
                    time.sleep(RETRY_BACKOFF_S * attempt)
                continue
            try:
                result = fn()
                self.trace.log(ev.t, handoff, agent, action, "ok", attempt)
                if attempt > 1:
                    self.stats["retries"] += 1
                return result
            except Exception as exc:  # noqa: BLE001 — real agent crash
                self.trace.log(ev.t, handoff, agent, action,
                               "retry" if attempt < MAX_ATTEMPTS else "error",
                               attempt, detail=repr(exc)[:120])
                if attempt < MAX_ATTEMPTS:
                    self.stats["retries"] += 1
                    time.sleep(RETRY_BACKOFF_S * attempt)
        self.trace.log(ev.t, handoff, agent, "fallback", "fallback", MAX_ATTEMPTS,
                       detail=f"stage '{agent}' exhausted after {MAX_ATTEMPTS} attempts")
        self.stats["fallbacks"] += 1
        return None

    # ------------------------------------------------------------ main flow

    def process_event(self, ev) -> list[dict]:
        """Fold one event into shared state; return personalized packets (or [])."""
        # ingestion stage is dependable by design (state consistency contract);
        # chaos injection only targets the agent stages below
        self.engine.update(ev)
        self.trace.log(ev.t, "ingest -> engine", "engine",
                       "fold event -> MatchState", "ok", 1)

        moment = self._run_stage(ev, "engine", "interpreter", "detect key moment",
                                 lambda: self.detector.detect(ev, self.state))
        if not moment:
            return []

        self.stats["moments"] += 1
        expl = self._run_stage(ev, "interpreter", "moment-explainer",
                               "ground explanation in MatchState",
                               lambda: self.explainer.explain(moment, self.state))
        if expl is None:
            # explainer is pure-deterministic; exhausted => drop moment, never stall
            return []

        narrative = self._run_stage(ev, "moment-explainer", "narrator",
                                    "render narrative packet",
                                    lambda: self.narrator.render(expl, self.state))
        if narrative is None:
            # fallback: broadcast continues on headline-grade copy (still grounded)
            narrative = self._degraded_narrative(expl)

        packets: list[dict] = []
        for profile in self.profiles:
            out = self._run_stage(ev, "narrator", "personalizer",
                                  f"personalize '{profile.type}' lang={profile.lang}",
                                  lambda p=profile: self.personalizer.render(
                                      narrative, expl, self.state, profile=p))
            if out is None:
                # fallback: raw narrative packet for this audience (no re-framing)
                out = narrative.to_dict()
                out["audience"] = profile.as_dict()
                out["focus"] = {"kind": "match", "through": None}
                out["trace"] = dict(out.get("trace", {}))
                out["trace"]["personalizer"] = "fallback"
            packets.append(out)
            self.stats["packets"] += 1
        return packets

    @staticmethod
    def _degraded_narrative(expl: dict):
        """Minimal narrative packet straight from the explainer copy."""
        from agents.narrator import NarrativePacket
        return NarrativePacket(
            moment_id=expl["moment_id"], t=float(expl["t"]), clock=expl["clock"],
            kind=expl["kind"], priority=expl["priority"],
            headline=expl["headline"], story=expl["headline"],
            stat_lines=expl.get("stat_lines", []),
            overlay={"duration_s": OVERLAY_DURATION.get(expl["priority"], 4.0),
                     "style": "neutral", "timed_for_overlay": True},
            trace={"narrator": "fallback"},
        )
