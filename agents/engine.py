"""StatsEngine — folds the synthetic event stream into MatchState.

Deterministic aggregation over events: possession, pass quality, shots/xG,
momentum, pressure index, field tilt, player aggregates. Volume>velocity is
the goal: every downstream "explanation" must be traceable to values here.
"""

from __future__ import annotations

from typing import Optional

from agents.state import (
    FINAL_THIRD_LEN,
    MOMENTUM_WEIGHTS,
    ROLLING_WINDOW_S,
    MatchState,
    distance_to_goal,
    event_clock,
    xt_value,
)
from simulator import Event


class StatsEngine:
    """Consumes Event stream; mutates a MatchState via update()."""

    def __init__(self, state: MatchState):
        self.state = state

    def update(self, ev: Event) -> None:
        s = self.state
        s.t = ev.t
        s.recent_events.append(self._lean(ev))

        # momentum decay to current event time
        s._update_momentum_clock(ev.t)

        handled = getattr(self, "_handle_" + ev.event_type.lower(), None)
        if handled:
            handled(ev)

        s.momentum_series.append((ev.t, s.momentum))

        # periodic trim of rolling logs
        cutoff = ev.t - 2 * ROLLING_WINDOW_S
        while s._touch_log and s._touch_log[0][0] < cutoff:
            s._touch_log.popleft()
        while s._pressure_log and s._pressure_log[0][0] < cutoff:
            s._pressure_log.popleft()

    # -- event handling ------------------------------------------------

    def _lean(self, ev: Event) -> dict:
        """Compact dict for log persistence (json.dumps-friendly)."""
        d = {"type": ev.event_type, "t": round(ev.t, 1)}
        if ev.team:
            d["team"] = ev.team
        if ev.player:
            d["player"] = ev.player
        if ev.outcome:
            d["outcome"] = ev.outcome
        if ev.event_type == "PASS":
            d["pass_length"] = ev.extra.get("pass_length")
            d["pass_difficulty"] = ev.extra.get("pass_difficulty")
        if ev.event_type in ("SHOT", "GOAL"):
            d["xg"] = ev.extra.get("xg")
        return d

    @staticmethod
    def _final_third(team: str, half: int, x: float, y: Optional[float]) -> bool:
        # final third zone relative to the goal the team attacks
        if (team == "HOME") == (half == 1):
            return x >= FINAL_THIRD_LEN
        return x <= 105.0 - FINAL_THIRD_LEN

    def _handle_pass(self, ev: Event) -> None:
        s = self.state
        team = ev.team or s.possession_team
        completed = ev.outcome == "COMPLETE"

        p = s.passes[team]
        p["attempts"] += 1
        length = ev.extra.get("pass_length") or 0.0
        diff = ev.extra.get("pass_difficulty") or 0.0
        if completed:
            p["completed"] += 1
            p["length_sum"] += length
            p["difficulty_sum"] += diff
            if diff >= 0.5:
                p["hard_completed"] += 1

        # player aggregate
        rec = s.player_passes.setdefault(ev.player or "?", {"team": team, "attempts": 0, "completed": 0})
        rec["attempts"] += 1
        if completed:
            rec["completed"] += 1

        # possession touch
        s._touch_log.append((ev.t, team))
        s._cumulative_touches[team] += 1
        s.possession_team = team

        # field tilt touch
        if ev.x is not None:
            s._total_touches += 1
            if self._final_third(team, s.half, ev.x, ev.y):
                s._final_third_touches[team] += 1

        # momentum + xT both only on completed passes
        if completed:
            s.momentum += MOMENTUM_WEIGHTS["PASS"] * (1.0 if team == "HOME" else -1.0)
            x_start = xt_value(s.half, team, ev.x, ev.y)
            x_end = xt_value(s.half, team, ev.to_x, ev.to_y)

            p["xt_gained"] += max(0.0, x_end - x_start)

    def _handle_shot(self, ev: Event) -> None:
        self._shot_common(ev, goal=False)

    def _handle_goal(self, ev: Event) -> None:
        self._shot_common(ev, goal=True)

    def _shot_common(self, ev: Event, goal: bool) -> None:
        s = self.state
        team = ev.team or s.possession_team
        sh = s.shots[team]
        sh["attempts"] += 1
        xg = float(ev.extra.get("xg") or 0.0)
        speed = float(ev.extra.get("shot_speed_kmh") or 0.0)
        sh["xg_sum"] += xg
        sh["speed_sum"] += speed
        if goal:
            sh["goals"] += 1
            s.score[team] += 1
            s.goal_log.append({
                "t": ev.t, "clock": event_clock(ev.t), "team": team,
                "player": ev.player, "xg": round(xg, 3),
                "distance_m": ev.extra.get("distance_to_goal"),
                "speed_kmh": round(speed, 1),
            })

        s._touch_log.append((ev.t, team))
        s._cumulative_touches[team] += 1
        s.possession_team = team

        if ev.x is not None:
            s._total_touches += 1
            if self._final_third(team, s.half, ev.x, ev.y):
                s._final_third_touches[team] += 1

        s.momentum += (MOMENTUM_WEIGHTS["SHOT"] + 4.0 * xg) * (1.0 if team == "HOME" else -1.0)

        if goal:
            s.momentum += MOMENTUM_WEIGHTS["GOAL"] * (1.0 if team == "HOME" else -1.0)
        # goal is momentum-nulling for scoreboard purposes; cap magnitude
        s.momentum = max(-1.5, min(1.5, s.momentum))

    def _handle_pressure(self, ev: Event) -> None:
        s = self.state
        team = ev.team or "AWAY"
        intensity = float(ev.extra.get("intensity") or 0.3)
        s._pressure_log.append((ev.t, team, intensity))
        s.momentum += (MOMENTUM_WEIGHTS["PRESSURE"] * intensity) * (1.0 if team == "HOME" else -1.0)

    def _handle_tackle(self, ev: Event) -> None:
        team = ev.team or "HOME"
        self.state.momentum += MOMENTUM_WEIGHTS["TACKLE"] * (1.0 if team == "HOME" else -1.0)

    def _handle_interception(self, ev: Event) -> None:
        team = ev.team or "HOME"
        self.state.momentum += MOMENTUM_WEIGHTS["INTERCEPTION"] * (1.0 if team == "HOME" else -1.0)

    def _handle_foul(self, ev: Event) -> None:
        team = ev.team or "HOME"
        self.state.momentum += MOMENTUM_WEIGHTS["FOUL"] * (1.0 if team == "HOME" else -1.0)

    def _handle_card_yellow(self, ev: Event) -> None:
        s = self.state
        team = ev.team or "?"
        s.cards.append({"t": ev.t, "clock": event_clock(ev.t), "team": team, "player": ev.player, "card": "YELLOW"})
        s.momentum += MOMENTUM_WEIGHTS["CARD_YELLOW"] * (1.0 if team == "HOME" else -1.0)

    def _handle_card_red(self, ev: Event) -> None:
        s = self.state
        team = ev.team or "?"
        s.cards.append({"t": ev.t, "clock": event_clock(ev.t), "team": team, "player": ev.player, "card": "RED"})
        s.momentum += MOMENTUM_WEIGHTS["CARD_RED"] * (1.0 if team == "HOME" else -1.0)

    def _handle_half_end(self, ev: Event) -> None:
        self.state.half = 2  # next play is half 2

    def _handle_match_end(self, ev: Event) -> None:
        self.state.winner_at_end = True
