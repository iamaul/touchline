"""ExplainerAgent — says WHY a moment matters, grounded in MatchState.

Contract with the rest of the pipeline:

  in:  Moment (from MomentDetector) + MatchState snapshot
  out: Explanation dict {moment_id, headline, why, stat_lines[], rhythm}

Hard rule: every claim in `why` must reference a value present in the
moment's `data` or the state snapshot. Templates interpolate real numbers
only — no invented facts. The Narrator agent (Day 4) re-renders this copy;
an LLM pass can restyle the `why` later, but the facts stay identical.

`control vs chaos` (hackathon explainability axis) is classified here:
  control  — one rolling-possession share >= 60% and low both-side pressure
  chaos    — pressure summed on both sides + recent shots within window
  balanced — everything else
"""

from __future__ import annotations

from agents.state import event_clock
from simulator import Team

# rhythm thresholds (same grounded basis as detector windows)
RHYTHM_CONTROL_POSSESSION = 62.0
RHYTHM_CHAOS_PRESSURE_SUM = 90.0
RHYTHM_CHAOS_PRESSURE_EACH = 25.0


def _rhythm(state) -> str:
    snap = state.snapshot()
    rolling = snap["possession"]["rolling_5min"]
    pres = snap["pressure_index"]
    dominant = max(rolling, key=rolling.get)
    if rolling[dominant] >= RHYTHM_CONTROL_POSSESSION and sum(pres.values()) < RHYTHM_CHAOS_PRESSURE_SUM:
        return f"control ({state.team_name(dominant)} owns {rolling[dominant]:.0f}% of the last 5 minutes)"
    if sum(pres.values()) >= RHYTHM_CHAOS_PRESSURE_SUM and min(pres.values()) >= RHYTHM_CHAOS_PRESSURE_EACH:
        return "chaos (both sides pressing, turnovers everywhere)"
    return "balanced midfield rhythm"


def _stat_line(label: str, home: str, away: str) -> dict:
    return {"label": label, "HOME": home, "AWAY": away}


class ExplainerAgent:

    def explain(self, moment, state) -> dict:
        head = self._headline(moment, state)
        why, stats = self._why(moment, state)
        return {
            "moment_id": moment.id,
            "t": round(moment.t, 1),
            "clock": event_clock(moment.t),
            "kind": moment.kind,
            "team": moment.team,
            "player": moment.player,
            "priority": moment.priority,
            "scoreline": f"{state.score['HOME']}-{state.score['AWAY']}",
            "headline": head,
            "why": why,
            "stat_lines": stats,
            "rhythm": _rhythm(state),
            "moments_data": moment.data,
        }

    # ------------------------------------------------------------- copy

    def _headline(self, moment, state) -> str:
        team_name = state.team_name(moment.team) if moment.team else "Both sides"
        if moment.kind == "GOAL":
            return f"GOAL {team_name} — {moment.player} finishes ({moment.data['score_after']['HOME']}-{moment.data['score_after']['AWAY']})"
        if moment.kind == "BIG_CHANCE":
            return f"{moment.player} wastes a chance worth xG {moment.data['xg']}"
        if moment.kind == "END_TO_END":
            return "Chaos: chances at both ends seconds apart"
        if moment.kind == "MOMENTUM_SWING":
            return f"{team_name} on top — momentum shifts {moment.data['momentum_delta_2min']:+.2f}"
        if moment.kind == "PRESSURE_SURGE":
            return f"{team_name} ramping up the press"
        return f"{moment.kind} at {event_clock(moment.t)}"

    def _why(self, moment, state):
        d = moment.data
        stats: list[dict] = []
        team_name = state.team_name(moment.team) if moment.team else "the game"

        if moment.kind == "GOAL":
            dist = d.get("distance_to_goal")
            xg = d.get("xg")
            speed = d.get("shot_speed_kmh")
            why = (
                f"{moment.player} scores from {dist}m — a chance worth xG {xg}, "
                f"struck at {speed} km/h. The scoreboard moves to "
                f"{d['score_after']['HOME']}-{d['score_after']['AWAY']}, and momentum is now "
                f"{d['momentum']:+.2f} in favour of {team_name}."
            )
            snap = state.snapshot()
            stats = [
                _stat_line("Shot xG", f"{xg:.2f}", "—"),
                _stat_line("Distance to goal", f"{dist}m", "—"),
                _stat_line("Ball speed", f"{speed:.0f} km/h", "—"),
                _stat_line("Shot xG total", f"{snap['shots']['HOME']['xg_total']}", f"{snap['shots']['AWAY']['xg_total']}"),
                _stat_line("Momentum", f"{d['momentum']:+.2f}", ""),
            ]
            return why, stats

        if moment.kind == "BIG_CHANCE":
            dist = d.get("distance_to_goal")
            why = (
                f"{moment.player} got in from {dist}m for a chance worth xG {d['xg']} "
                f"({d['outcome']}). Misses from xG {d['xg']:.2f}+ positions tell on teams: "
                f"{team_name} outscored the expectation table there."
            )
            snap = state.snapshot()
            shots = snap["shots"][moment.team]  # snapshot keys, not raw state keys
            stats = [
                _stat_line("Shot xG", f"{d['xg']:.2f}", ""),
                _stat_line("Distance", f"{dist}m", ""),
                _stat_line("Team xG total", f"{shots['xg_total']}", ""),
                _stat_line("Team attempts", f"{shots['attempts']}", ""),
            ]
            return why, stats


        if moment.kind == "END_TO_END":
            why = (
                f"Both teams needed chances inside {d['gap_s']}s of each other "
                f"({', '.join(d['teams_involved'])}) — classic chaos rhythm, "
                f"transition-heavy and low on structure."
            )
            stats = [
                _stat_line("Chance gap", f"{d['gap_s']}s", ""),
                _stat_line("Momentum", f"{d['momentum']:+.2f}", ""),
            ]
            return why, stats

        if moment.kind == "MOMENTUM_SWING":
            poss = d["possession_rolling"]
            acc = d["pass_accuracy"]
            pteam = poss[moment.team]
            # possession claims only when the possession share actually agrees
            # with the swing direction (grounded-copy rule)
            if pteam >= 57.0:
                control = (
                    f"{team_name} held {pteam:.0f}% of the ball over the last 5 minutes "
                    f"at {acc[moment.team]:.0f}% pass accuracy — control is compounding."
                )
            elif pteam <= 43.0:
                control = (
                    f"{team_name} did this with only {pteam:.0f}% possession "
                    f"(vs {acc[moment.team]:.0f}% pass accuracy) — the push came from "
                    f"individual chances and defence attacks, not sustained control."
                )

            else:
                control = "No sustained possession advantage in the window — the swing came from chance events."
            why = f"{team_name} swung the game {d['momentum_delta_2min']:+.2f} in 2 minutes. {control}"
            stats = [
                _stat_line("Momentum Δ (2m)", f"{d['momentum_delta_2min']:+.2f}", ""),
                _stat_line("Possession (5m)", f"{poss['HOME']}%", f"{poss['AWAY']}%"),
                _stat_line("Pass accuracy", f"{acc['HOME']}%", f"{acc['AWAY']}%"),
            ]
            return why, stats


        if moment.kind == "PRESSURE_SURGE":
            why = (
                f"{team_name} registered {d['pressure_events_4min']} pressure events over "
                f"4 minutes (intensity {d['pressure_intensity_4min']:.2f}) — sustained press, "
                f"ball may be dropped soon."
            )
            stats = [
                _stat_line("Pressure events (4m)", f"{d['pressure_events_4min']}", ""),
                _stat_line("Press intensity", f"{d['pressure_intensity_4min']:.2f}", ""),
                _stat_line("Momentum", f"{d['momentum']:+.2f}", ""),
            ]
            return why, stats

        why = f"{moment.kind} at {event_clock(moment.t)}."
        return why, stats
