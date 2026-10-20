"""Moment detection (Interpreter).

Slides over the event stream + MatchState and emits candidate key moments
when football-meaningful signal crosses thresholds:

  GOAL             always a moment (priority 1)
  BIG_CHANCE       high-xG attempt that didn't score (near-miss drama)
  MOMENTUM_SWING    |Δmomentum| over the lookback window above threshold
  PRESSURE_SURGE    sustained press-intensity climb by one side
  END_TO_END        both teams create inside a short window (chaos)

Every moment carries the exact events and MatchState metrics that caused
it, so the Explainer can reason from data instead of inventing narrative.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from simulator import Event


# --------------------------------------------------------------- tuning

SWING_LOOKBACK_S = 120.0        # momentum delta window
SWING_THRESHOLD = 0.55          # |Δmomentum| to trigger a swing moment

SURGE_LOOKBACK_S = 240.0
SURGE_MIN_EVENTS = 3            # min pressure events in window
SURGE_INTENSITY_MIN = 2.2       # summed intensity in window
NEAR_MISS_XG = 0.25             # xG floor for BIG_CHANCE
END_TO_END_WINDOW_S = 45.0      # shots by both teams within this span
KIND_COOLDOWN_S = 90.0          # default spacing (goals have none)
PER_KIND_COOLDOWN = {
    "MOMENTUM_SWING": 240.0,
    "PRESSURE_SURGE": 180.0,
    "BIG_CHANCE": 75.0,
    "END_TO_END": 75.0,
}



PRIORITY = {"GOAL": 1, "BIG_CHANCE": 2, "END_TO_END": 2, "MOMENTUM_SWING": 2, "PRESSURE_SURGE": 3}


@dataclass
class Moment:
    id: str
    t: float
    kind: str
    team: Optional[str]            # primary team (None = neutral phases)
    player: Optional[str]
    priority: int
    data: dict = field(default_factory=dict)   # metrics snapshot used to trigger
    events: list = field(default_factory=list) # lean event dicts that caused it

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "t": round(self.t, 1),
            "kind": self.kind,
            "team": self.team,
            "player": self.player,
            "priority": self.priority,
            "data": self.data,
            "events": self.events,
        }


class MomentDetector:
    """Consumes (event, state-shape inputs) after each StatsEngine.update()."""

    def __init__(self):
        self._count = 0
        self._last_occurrence: dict[str, float] = {}
        self._recent_shot: Optional[tuple[float, str]] = None   # (t, team)
        self._recent_events: deque = deque(maxlen=40)

    # ------------------------------------------------------------- helpers

    def _cooldown_ok(self, kind: str, t: float) -> bool:
        if kind == "GOAL":
            return True
        last = self._last_occurrence.get(kind)
        gap = PER_KIND_COOLDOWN.get(kind, KIND_COOLDOWN_S)
        return last is None or (t - last) >= gap


    def _took(self, kind: str, t: float) -> None:
        self._last_occurrence[kind] = t

    def _lean(self, ev: Event) -> dict:
        d = {"type": ev.event_type, "t": round(ev.t, 1), "team": ev.team, "player": ev.player,
             "outcome": ev.outcome}
        if ev.event_type == "PASS":
            d["pass_length"] = ev.extra.get("pass_length")
        if ev.event_type in ("SHOT", "GOAL"):
            d["xg"] = ev.extra.get("xg")
            d["distance_to_goal"] = ev.extra.get("distance_to_goal")
        return d

    @staticmethod
    def _momentum_delta(state, t: float, lookback: float) -> float:
        """Momentum now minus momentum at t-lookback (from the sampled series)."""
        target = t - lookback
        past = state.momentum_series[0][1] if state.momentum_series else 0.0
        for tt, val in state.momentum_series:
            if tt <= target:
                past = val
            else:
                break
        return state.momentum - past

    @staticmethod
    def _pressure_window_sum(state, t: float, lookback: float) -> tuple[dict, dict]:
        counts = {"HOME": 0, "AWAY": 0}
        intensity = {"HOME": 0.0, "AWAY": 0.0}
        cutoff = t - lookback
        for tt, team, inten in state._pressure_log:
            if tt >= cutoff:
                counts[team] += 1
                intensity[team] += inten
        return counts, intensity

    # ------------------------------------------------------------- main

    def detect(self, ev: Event, state) -> Optional[Moment]:
        self._recent_events.append(self._lean(ev))
        candidates: list[Moment] = []

        kind, team, player, priority, data = self._classify(ev, state)
        if kind and self._cooldown_ok(kind, ev.t):
            mom = Moment(
                id=f"m{self._count:04d}", t=ev.t, kind=kind, team=team, player=player,
                priority=priority, data=data,
                events=list(self._recent_events),
            )
            self._count += 1
            self._took(kind, ev.t)
            candidates.append(mom)

        for c in candidates:
            c.scoreline = dict(state.score)
        return candidates[0] if candidates else None

    # ------------------------------------------------------- classifiers

    def _classify(self, ev: Event, state):
        if ev.event_type == "GOAL":
            return "GOAL", ev.team, ev.player, PRIORITY["GOAL"], {
                "xg": ev.extra.get("xg"),
                "distance_to_goal": ev.extra.get("distance_to_goal"),
                "shot_speed_kmh": ev.extra.get("shot_speed_kmh"),
                "score_after": dict(state.score),
                "momentum": round(state.momentum, 3),
            }

        if ev.event_type == "SHOT":
            xg = float(ev.extra.get("xg") or 0.0)
            # end-to-end: this shot and a previous shot by the other team within window
            if self._recent_shot and self._recent_shot[1] != (ev.team or "") \
                    and (ev.t - self._recent_shot[0]) <= END_TO_END_WINDOW_S \
                    and xg >= NEAR_MISS_XG:
                return "END_TO_END", None, None, PRIORITY["END_TO_END"], {
                    "gap_s": round(ev.t - self._recent_shot[0], 1),
                    "teams_involved": [self._recent_shot[1], ev.team],
                    "xg": round(xg, 3),
                    "momentum": round(state.momentum, 3),
                }
            self._recent_shot = (ev.t, ev.team or "")
            if xg >= NEAR_MISS_XG and ev.outcome != "ATTEMPT_GOAL":
                return "BIG_CHANCE", ev.team, ev.player, PRIORITY["BIG_CHANCE"], {
                    "xg": round(xg, 3),
                    "distance_to_goal": ev.extra.get("distance_to_goal"),
                    "outcome": ev.outcome,
                    "momentum": round(state.momentum, 3),
                }

        if ev.event_type in ("PRESSURE", "GOAL", "SHOT", "TACKLE", "INTERCEPTION", "PASS"):
            _, intensity = self._pressure_window_sum(state, ev.t, SURGE_LOOKBACK_S)
            best = max(intensity, key=intensity.get)
            if intensity[best] >= SURGE_INTENSITY_MIN:
                counts, _ = self._pressure_window_sum(state, ev.t, SURGE_LOOKBACK_S)
                if counts[best] >= SURGE_MIN_EVENTS:
                    delta = self._momentum_delta(state, ev.t, SWING_LOOKBACK_S)
                    return "PRESSURE_SURGE", best, ev.player, PRIORITY["PRESSURE_SURGE"], {
                        "pressure_intensity_4min": round(intensity[best], 2),
                        "pressure_events_4min": counts[best],
                        "momentum": round(state.momentum, 3),
                        "momentum_delta_2min": round(delta, 3),
                    }

            delta = self._momentum_delta(state, ev.t, SWING_LOOKBACK_S)
            if abs(delta) >= SWING_THRESHOLD:
                swing_team = "HOME" if delta > 0 else "AWAY"
                snap = state.snapshot()
                return "MOMENTUM_SWING", swing_team, None, PRIORITY["MOMENTUM_SWING"], {
                    "momentum_delta_2min": round(delta, 3),
                    "momentum": round(state.momentum, 3),
                    "possession_rolling": snap["possession"]["rolling_5min"],
                    "pass_accuracy": {
                        "HOME": snap["passes"]["HOME"]["accuracy_pct"],
                        "AWAY": snap["passes"]["AWAY"]["accuracy_pct"],
                    },
                }

        return None, None, None, 0, {}
