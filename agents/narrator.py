"""NarratorAgent — renders explanations into overlay-ready narrative packets.

Output contract (machine-readable, timed — the shape the web overlay and
any external graphics renderer consume):

  {
    moment_id, t (sim seconds), clock, kind, priority, lang,
    headline, story, stat_lines[],
    overlay: {duration_s, style},
    trace: {"narrator": "llm" | "template"}
  }

LLM integration (when a provider is configured): the model may restyle
`story` phrasing. Facts are pinned in the prompt and re-substituted in code
afterwards whenever possible — the model never introduces new facts.
No provider configured -> deterministic broadcast template, pipeline still
runs (also the behaviour when the LLM call fails/timeout).
"""

from __future__ import annotations

from agents.llm import ChatConfig, chat
from agents.state import event_clock
from dataclasses import dataclass, field

# overlay duration by priority (seconds on screen)
OVERLAY_DURATION = {1: 6.0, 2: 4.5, 3: 3.0}

KIND_STYLE = {
    "GOAL": "explosion,line-break,call-the-moment",
    "BIG_CHANCE": "tension,near-miss",
    "END_TO_END": "breathless,speedy",
    "MOMENTUM_SWING": "analytical,building",
    "PRESSURE_SURGE": "foreboding,building",
}

_NARRATE_SYSTEM = (
    "You are a live football broadcast copywriter. Given a structured moment "
    "(facts fixed), rewrite ONLY the 'story' field: short broadcast voice, 1-2 "
    "sentences, no new facts, no invented statistics, keep the numbers given. "
    "Return just the rewritten story text."
)


@dataclass
class NarrativePacket:
    moment_id: str
    t: float
    clock: str
    kind: str
    priority: int
    lang: str = "en"
    headline: str = ""
    story: str = ""
    stat_lines: list = field(default_factory=list)
    overlay: dict = field(default_factory=dict)
    trace: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "moment_id": self.moment_id, "t": round(self.t, 1), "clock": self.clock,
            "kind": self.kind, "priority": self.priority, "lang": self.lang,
            "headline": self.headline, "story": self.story, "stat_lines": self.stat_lines,
            "overlay": self.overlay, "trace": self.trace,
        }


def _template_story(kind: str, team_name: str, expl: dict) -> str:
    """Deterministic 1-2 sentence broadcast story per kind (facts from expl)."""
    who = expl.get("player") or team_name
    if kind == "GOAL":
        return f"{who} finds the net for {team_name} and the ground erupts at {expl['clock']}."
    if kind == "BIG_CHANCE":
        return f"{who} gets in alone from {expl['moments_data'].get('distance_to_goal')}m — off the target, and a huge breath out."
    if kind == "END_TO_END":
        return f"Hands over the ball — {expl['scoreline']} keeps everyone on their toes."
    if kind == "MOMENTUM_SWING":
        return f"{team_name} grabs the game's rhythm and pushes the boundaries."
    if kind == "PRESSURE_SURGE":
        return f"The press is on from {team_name} — everything feels one bad touch away from cracking."
    return f"{expl['headline']}"


class NarratorAgent:

    def __init__(self, chat_cfg: Optional[ChatConfig] = None, use_llm: bool = True):
        self.cfg = chat_cfg
        self.use_llm = bool(chat_cfg) and use_llm

    def render(self, expl: dict, state) -> NarrativePacket:
        team_name = state.team_name(expl["team"]) if expl.get("team") else state.team_name("HOME")
        story = _template_story(expl["kind"], team_name, expl)
        used_llm = False
        if self.use_llm and self.cfg:
            grounded = json.dumps(


                {
                    "headline": expl["headline"],
                    "story_facts": story,
                    "kind": expl["kind"],
                    "clock": expl["clock"],
                    "scoreline": expl.get("scoreline"),
                    "stat_lines": [
                        {"label": s.get("label"), "HOME": s.get("HOME"), "AWAY": s.get("AWAY")}
                        for s in (expl.get("stat_lines") or [])[:3]
                    ],
                },
                ensure_ascii=False,
            )
            out = chat(self.cfg, [
                {"role": "system", "content": _NARRATE_SYSTEM},
                {"role": "user", "content": grounded},
            ], temperature=0.55, max_tokens=220)
            if out:
                # never extend the facts: keep it single-paragraph, trimmed
                story = out.strip().replace("\n", " ")
                used_llm = True

        return NarrativePacket(
            moment_id=expl["moment_id"],
            t=expl["t"],
            clock=expl["clock"],
            kind=expl["kind"],
            priority=expl["priority"],
            lang="en",
            headline=expl["headline"],
            story=story,
            stat_lines=[s for s in (expl.get("stat_lines") or [])],
            overlay={
                "duration_s": OVERLAY_DURATION.get(expl["priority"], 4.0),
                "style": KIND_STYLE.get(expl["kind"], "neutral"),
                "timed_for_overlay": True,
            },
            trace={"narrator": "llm" if used_llm else "template"},
        )


# json module needed for the grounded prompt serialization
import json  # noqa: E402

