"""MatchState — the shared match state consumed by every SecondSight agent.

Holds rolling and cumulative statistics derived from the synthetic event
stream. Downstream agents (Interpreter, Explainer, Narrator, Personalizer)
read MatchState through the orchestrator; all explanation must be grounded
in what is actually in here (no invented facts).
"""

from __future__ import annotations

import math
from collections import deque
from typing import Optional

from simulator import PITCH, Team

# --------------------------------------------------------------- constants

ROLLING_WINDOW_S = 300.0     # rolling stats window: last 5 simulated minutes
PRESSURE_WINDOW_S = 240.0    # pressure index window
MOMENTUM_TAU_S = 420.0       # momentum decay time constant (7 min)
FINAL_THIRD_LEN = PITCH["length"] * 2.0 / 3.0  # 70m line of the attacking end

# Momentum weights per event type (signed by team, scaled by context)
MOMENTUM_WEIGHTS = {
    "GOAL": 6.0,
    "SHOT": 2.0,        # + 4 * xG bonus at emit time
    "SAVE": 0.5,        # (not emitted by sim; reserved)
    "INTERCEPTION": 0.3,
    "TACKLE": 0.3,
    "FOUL": -0.1,       # conceding a foul is mildly momentum-negative
    "CARD_YELLOW": -0.8,
    "CARD_RED": -3.0,
    "PRESSURE": 0.4,    # scaled by intensity at emit time
    "PASS": 0.06,       # baseline, scaled by xT gain at emit time
}

SIX_YARD_FROM_END = 5.25


def event_clock(t: float) -> str:
    """Match clock seconds -> 'MM:SS' (90 min = 5400s)."""
    mm = int(t // 60)
    sec = int(t % 60)
    return f"{mm:02d}:{sec:02d}"


def attacked_goal(half: int, team: str) -> tuple[float, float]:
    """(x, y) centre of the goal `team` attacks given current half (mirrors sim)."""
    attacks_right = (team == "HOME") == (half == 1)
    gx = PITCH["length"] if attacks_right else 0.0
    return gx, PITCH["width"] / 2


def distance_to_goal(half: int, team: str, x: Optional[float], y: Optional[float]) -> Optional[float]:
    if x is None or y is None:
        return None
    gx, gy = attacked_goal(half, team)
    return math.hypot(x - gx, y - gy)


def xt_value(half: int, team: str, x: Optional[float], y: Optional[float]) -> float:
    """Crude expected-threat curve: value rises as the ball nears the attacked goal.

    xt = max(0, 1 - d/60)^2 — 0 deep in own half, ~1 at the goal mouth.
    Aggregated deltas approximate real xT chain-building logic without carrying
    a full Opta-style zone grid (v1 keeps the engine dependency-free).
    """
    d = distance_to_goal(half, team, x, y)

    if d is None:
        return 0.0
    return max(0.0, 1.0 - d / 60.0) ** 2


# --------------------------------------------------------------- state


class MatchState:
    """Aggregate container. Only the StatsEngine mutates it."""

    def __init__(self, arrivals_home: Team, arrivals_away: Team, seed: int | None = None):
        self.teams = {"HOME": arrivals_home, "AWAY": arrivals_away}
        self.seed = seed

        # Clock & meta
        self.t: float = 0.0
        self.half: int = 1
        self.score: dict = {"HOME": 0, "AWAY": 0}
        self.cards: list = []          # {t, team, player, card}
        self.winner_at_end: bool = False

        # Possession
        self.possession_team: str = "HOME"
        # rolling window material: list of (t, team) for each possession-bound event
        self._touch_log: deque = deque()
        self._cumulative_touches: dict = {"HOME": 0, "AWAY": 0}


        # Passes
        self.passes: dict = {
            "HOME": {"attempts": 0, "completed": 0, "length_sum": 0.0, "difficulty_sum": 0.0,
                     "hard_completed": 0, "xt_gained": 0.0},
            "AWAY": {"attempts": 0, "completed": 0, "length_sum": 0.0, "difficulty_sum": 0.0,
                     "hard_completed": 0, "xt_gained": 0.0},
        }

        # Shots & goals
        self.shots: dict = {
            "HOME": {"attempts": 0, "goals": 0, "xg_sum": 0.0, "speed_sum": 0.0},
            "AWAY": {"attempts": 0, "goals": 0, "xg_sum": 0.0, "speed_sum": 0.0},
        }
        self.goal_log: list = []  # {t, team, player, xg, dist}

        # Momentum (signed scalar: + HOME ascends, - AWAY ascends)
        self.momentum: float = 0.0
        self._last_momentum_t: float = 0.0
        self.momentum_series: deque = deque(maxlen=600)  # (t, value)

        # Pressure index (0..100 per team, rolling)
        self._pressure_log: deque = deque()  # (t, team, intensity)

        # Field tilt: touches in the final third per team
        self._final_third_touches: dict = {"HOME": 0, "AWAY": 0}
        self._total_touches: int = 0

        # Player-level aggregates (for identification/leaderboards)
        self.player_passes: dict = {}  # name -> {"completed": n, "attempts": n}

        # Recent events for explainability trace + overlay renderer
        self.recent_events: deque = deque(maxlen=25)

    # ------------------------------------------------------------ helpers

    def team_name(self, team: str) -> str:
        return self.teams[team].name

    def _update_momentum_clock(self, t: float) -> None:
        dt = t - self._last_momentum_t
        if dt > 0:
            self.momentum *= math.exp(-dt / MOMENTUM_TAU_S)
            self._last_momentum_t = t

    # ------------------------------------------------------------ snapshot

    def snapshot(self) -> dict:
        """Full machine-readable snapshot — the packet shape the UI/agents consume."""
        # possession from touch log (rolling) + cumulative counters
        cutoff = self.t - ROLLING_WINDOW_S
        touches = list(self._touch_log)
        rolling_counts = {"HOME": 0, "AWAY": 0}
        cumulative_counts = {"HOME": self._cumulative_touches["HOME"], "AWAY": self._cumulative_touches["AWAY"]}

        parts = []
        for tt, team in touches:
            if tt >= cutoff:
                rolling_counts[team] += 1


        def pct(d: dict) -> dict:
            tot = d["HOME"] + d["AWAY"]
            if tot == 0:
                return {"HOME": 50.0, "AWAY": 50.0}
            return {
                "HOME": round(100.0 * d["HOME"] / tot, 1),
                "AWAY": round(100.0 * d["AWAY"] / tot, 1),
            }

        # pressure index: rolling intensity sum per team, normalized
        rcut = self.t - PRESSURE_WINDOW_S
        pressure_counts = {"HOME": 0.0, "AWAY": 0.0}
        for tt, team, intensity in self._pressure_log:
            if tt >= rcut:
                pressure_counts[team] += intensity
        pressure_idx = {
            team: round(min(100.0, 100.0 * v / (PRESSURE_WINDOW_S / 60.0)), 1)
            for team, v in pressure_counts.items()
        }

        pass_snap = {}
        for team, p in self.passes.items():
            att, comp = p["attempts"], p["completed"]
            pass_snap[team] = {
                "attempts": att,
                "completed": comp,
                "accuracy_pct": round(100.0 * comp / att, 1) if att else 0.0,
                "avg_length_m": round(p["length_sum"] / comp, 1) if comp else 0.0,
                "hard_completed": p["hard_completed"],  # completed passes with difficulty >= 0.5
                "xt_gained": round(p["xt_gained"], 3),
            }

        shot_snap = {}
        for team, s in self.shots.items():
            shot_snap[team] = {
                "attempts": s["attempts"],
                "goals": s["goals"],
                "xg_total": round(s["xg_sum"], 2),
                "avg_speed_kmh": round(s["speed_sum"] / s["attempts"], 1) if s["attempts"] else 0.0,
            }

        return {
            "t": round(self.t, 1),
            "clock": event_clock(self.t),
            "half": self.half,
            "teams": {
                "HOME": {"id": "HOME", "name": self.teams["HOME"].name, "color": self.teams["HOME"].color},
                "AWAY": {"id": "AWAY", "name": self.teams["AWAY"].name, "color": self.teams["AWAY"].color},
            },
            "score": dict(self.score),
            "possession": {
                "rolling_5min": pct(rolling_counts),
                "cumulative": pct(cumulative_counts),
            },
            "passes": pass_snap,
            "shots": shot_snap,
            "momentum": {
                "value": round(self.momentum, 3),
                "series": [(round(tt, 1), round(v, 3)) for tt, v in list(self.momentum_series)[-90:]],
            },
            "pressure_index": pressure_idx,
            "field_tilt": {
                team: round(100.0 * self._final_third_touches[team] / max(1, self._total_touches), 1)
                for team in ("HOME", "AWAY")
            },
            "goal_log": list(self.goal_log),
            "cards": list(self.cards),
            "last_events": list(self.recent_events)[-12:],
        }
