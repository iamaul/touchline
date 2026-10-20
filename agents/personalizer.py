"""PersonalizerAgent — same moment, genuinely different audience experiences.

Viewer profiles:
  type       "analyst" (dense numbers) | "casual" (plain language, 2 chips)
  club       favorite club name (moment framed through the club when relevant)
  player     favorite player (framed when they feature in the moment)
  lang       narrative language (LLM translation when provider configured)

Packet contract:
  {
    ...narrative fields...,            (replaced keys: headline, story, stat_lines)
    audience: {"type", "club", "player", "lang"},
    focus: {"kind": "self"|"team"|"match"|"favorite", "through": str|None},
    trace: {..., "personalizer": "llm" | "template"}
  }
"""

from __future__ import annotations

from agents.llm import ChatConfig, chat
from agents.narrator import NarrativePacket

CHIPS_CASUAL = 2

_TRANSLATE_SYSTEM = (
    "You are a broadcast translation tool for live football overlay graphics. "
    "Translate the given headline and story faithfully into the requested "
    "language. Keep every number exactly as given. Do not add facts. "
    "Return two lines only:\nHEADLINE: <translated headline>\nSTORY: <translated story>"
)


def translate_headline_story(cfg: ChatConfig, headline: str, story: str, lang: str):
    out = chat(cfg, [
        {"role": "system", "content": _TRANSLATE_SYSTEM},
        {"role": "user", "content": f"Language: {lang}\nHEADLINE: {headline}\nSTORY: {story}"},
    ], temperature=0.2, max_tokens=260)
    if not out:
        return None
    head, sto = None, None
    for line in out.splitlines():
        low = line.lower()
        if low.startswith("headline:") and head is None:
            head = line.split(":", 1)[1].strip()
        elif low.startswith("story:") and sto is None:
            sto = line.split(":", 1)[1].strip()
    if head and sto:
        return head, sto
    return None


class ViewerProfile:
    def __init__(self, type_: str = "casual", club: str | None = None,
                 player: str | None = None, lang: str = "en"):
        assert type_ in ("analyst", "casual")
        self.type = type_
        self.club = club
        self.player = player
        self.lang = lang

    def as_dict(self) -> dict:
        return {"type": self.type, "club": self.club, "player": self.player, "lang": self.lang}


class PersonalizerAgent:

    def __init__(self, chat_cfg: Optional[ChatConfig] = None, use_llm: bool = True):
        self.cfg = chat_cfg
        self.use_llm = bool(chat_cfg) and use_llm

    # ------------------------------------------------------------- focus

    def _focus(self, expl: dict, state, profile: ViewerProfile) -> dict:
        """Which lens the packet is framed through (grounded: expl has team/player)."""
        if profile.player and expl.get("player") == profile.player:
            return {"kind": "favorite-player", "through": profile.player}
        if profile.club:
            club_side = next(
                (side for side, t in state.teams.items() if t.name == profile.club), None
            )
            if club_side is not None and expl.get("team") == club_side:
                return {"kind": "favorite-club", "through": profile.club}
        return {"kind": "match", "through": None}

    # ------------------------------------------------------------- copy

    def _render_analyst(self, packet: NarrativePacket, expl: dict) -> tuple[str, str, list]:
        """Analyst keeps numeric density, headline technical."""
        head = packet.headline if packet.kind == "GOAL" else f"[{packet.kind}] {packet.headline}"
        story = packet.story
        stats = list(packet.stat_lines)
        return head, story, stats

    def _render_casual(self, packet: NarrativePacket, expl: dict) -> tuple[str, str, list]:
        """Casual fan: short, plain, two-chip cap, emotional hook."""
        head = packet.headline
        if packet.kind == "GOAL":
            story = packet.story
        else:
            # keep the most emotional clause: story already 1-2 sentences
            story = packet.story.split(". ")[0] + "." if ". " in packet.story else packet.story
        stats = packet.stat_lines[:CHIPS_CASUAL]
        return head, story, stats

    def _apply_focus_copy(self, head: str, story: str, focus: dict) -> tuple[str, str]:
        """Grounded personal flavor: favorite player featured -> lead with their name.
        Nothing invented, just ordering of facts we already have."""
        if focus["kind"] == "favorite-player" and not head.startswith(focus["through"]):
            head = f"{focus['through']} spotlight — {head}"
        return head, story

    def render(self, packet: NarrativePacket, expl: dict, state, profile: ViewerProfile) -> dict:
        d = packet.to_dict()
        used_llm = False

        if profile.type == "analyst":
            head, story, stats = self._render_analyst(packet, expl)
        else:
            head, story, stats = self._render_casual(packet, expl)

        focus = self._focus(expl, state, profile)
        head, story = self._apply_focus_copy(head, story, focus)

        out = dict(d)
        out["headline"] = head
        out["story"] = story
        out["stat_lines"] = stats
        out["focus"] = focus

        if profile.lang and profile.lang.lower() not in ("en", "english") and self.use_llm and self.cfg:
            translated = translate_headline_story(self.cfg, head, story, profile.lang)
            if translated:
                out["headline"], out["story"] = translated
                out["lang"] = profile.lang
                used_llm = True

        out["trace"] = dict(d.get("trace", {}))
        out["trace"]["personalizer"] = "llm" if used_llm else "template"
        out["audience"] = profile.as_dict()
        return out
