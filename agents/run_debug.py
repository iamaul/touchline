"""Live console debug view of SecondSight stats — end-to-end Day 2 check.

Streams a synthetic match through the stats engine and renders rolling
possession, momentum, pressure, pass quality and xG, updating on a cadence:

    python -m agents.run_debug                       # default seed, speed 60x
    python -m agents.run_debug --seed 7 --speed 300  # fast-forward whole match
    python -m agents.run_debug --interval-sim 120    # refresh every 2 sim-min
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from agents import MatchState, StatsEngine
from agents.state import event_clock
from simulator import Event, MatchSimulator, default_teams

BAR_WIDTH = 32


def bars(left: float, right: float, width: int = BAR_WIDTH) -> str:
    total = left + right
    if total <= 0:
        left_frac = 0.5
    else:
        left_frac = left / total
    filled = round(width * left_frac)
    return "█" * filled + "░" * (width - filled)


def momentum_bar(value: float, width: int = BAR_WIDTH) -> str:
    """value in [-1, 1]: + HOME pulls left, - AWAY pulls right."""
    frac = (max(-1.0, min(1.0, value)) + 1.0) / 2.0
    filled = round(width * frac)
    nudge = "●" if 0 < filled < width else ""
    return "█" * filled + nudge + "░" * (width - filled)


def render(s) -> str:
    snap = s.snapshot()
    home = snap["teams"]["HOME"]["name"]
    away = snap["teams"]["AWAY"]["name"]
    score = snap["score"]
    poss = snap["possession"]["rolling_5min"]
    cum = snap["possession"]["cumulative"]
    ps_h = snap["passes"]["HOME"]
    ps_a = snap["passes"]["AWAY"]
    sh_h = snap["shots"]["HOME"]
    sh_a = snap["shots"]["AWAY"]
    mom = snap["momentum"]["value"]
    pres = snap["pressure_index"]
    tilt = snap["field_tilt"]

    lines = []
    lines.append("─" * 62)
    lines.append(
        f"  SecondSight  |  {home} {score['HOME']} - {score['AWAY']} {away}"
        f"  |  {snap['clock']}  ({'1st' if snap['half'] == 1 else '2nd'} half)"
    )
    lines.append("─" * 62)
    lines.append("")
    lines.append(f"  Possession (last 5 min)   {poss['HOME']:4.1f} {bars(poss['HOME'], poss['AWAY'])} {poss['AWAY']:<5.1f}")
    lines.append(f"  Possession (cumulative)   {cum['HOME']:4.1f} {bars(cum['HOME'], cum['AWAY'])} {cum['AWAY']:<5.1f}")
    lines.append(f"  Field tilt                {tilt['HOME']:4.1f} {bars(tilt['HOME'], tilt['AWAY'])} {tilt['AWAY']:<5.1f}")
    lines.append(f"  Momentum                  HOME {mom:+.2f} {momentum_bar(mom)} AWAY {-mom:+.2f}")

    lines.append(f"  Pressure index            HOME {pres['HOME']:5.1f}  /  AWAY {pres['AWAY']:5.1f}")
    lines.append("")
    lines.append(f"  Passes        HOME {ps_h['completed']}/{ps_h['attempts']} ({ps_h['accuracy_pct']}% acc, {ps_h['avg_length_m']}m avg)")
    lines.append(f"                AWAY {ps_a['completed']}/{ps_a['attempts']} ({ps_a['accuracy_pct']}% acc, {ps_a['avg_length_m']}m avg)")
    lines.append(f"  Shots         HOME {sh_h['attempts']} (xG {sh_h['xg_total']})   AWAY {sh_a['attempts']} (xG {sh_a['xg_total']})")
    lines.append("")
    if snap["goal_log"]:
        lines.append("  Goals:")
        for g in snap["goal_log"]:
            lines.append(f"    {g['clock']}  {s.team_name(g['team'])}  {g['player']}  (xG {g['xg']}, {g['distance_m']}m, {g['speed_kmh']}km/h)")
    if snap["cards"]:
        lines.append("  Cards:")
        for c in snap["cards"]:
            lines.append(f"    {c['clock']}  {s.team_name(c['team'])}  {c['player']}  ({c['card']})")
    lines.append("")
    le = snap["last_events"][-5:]
    lines.append("  Recent events:")
    for e in le:
        name = s.team_name(e["team"]) if e.get("team") else "-"
        player = e.get("player") or ""
        line = f"    {event_clock(e['t'])}  {e['type']:<14} {name:<22} {player}"
        if e["type"] == "PASS" and e.get("outcome"):
            line += f"  {e['outcome']} ({e.get('pass_length')}m, diff {e.get('pass_difficulty')})"
        lines.append(line)
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="SecondSight live debug console")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--speed", type=float, default=60.0, help="sim seconds per wall second")
    ap.add_argument("--interval-sim", type=float, default=60.0, help="render cadence in sim seconds")
    ap.add_argument("--json-out", default=None, help="also append snapshots to a JSONL file")
    ap.add_argument("--state-out", default=None, help="write final snapshot JSON to file")
    ap.add_argument("--clear", action="store_true", help="clear terminal each render")
    args = ap.parse_args()

    home_team, away_team = default_teams(args.seed)
    state = MatchState(home_team, away_team, seed=args.seed)
    engine = StatsEngine(state)
    simulator = MatchSimulator(seed=args.seed, speed=args.speed)

    jsonl = open(args.json_out, "a") if args.json_out else None
    next_render_t = 0.0
    rendered_events = 0

    for ev in simulator.run():
        engine.update(ev)
        rendered_events += 1
        if ev.t >= next_render_t or ev.event_type == "MATCH_START":
            view = render(state)
            if args.clear:
                os.system("cls" if os.name == "nt" else "clear 2>/dev/null || true")
            print(view, flush=True)
            next_render_t = ev.t + args.interval_sim

        if jsonl is not None and rendered_events % 25 == 0:
            jsonl.write(json.dumps(state.snapshot()) + "\n")
            jsonl.flush()

    if jsonl:
        jsonl.write(json.dumps(state.snapshot()) + "\n")
        jsonl.close()
    print(f"\n[done] {rendered_events} events consumed. Final score "
          f"{state.score['HOME']}-{state.score['AWAY']}", flush=True)

    if args.state_out:
        with open(args.state_out, "w") as f:
            json.dump(state.snapshot(), f, indent=2)
        print(f"[saved] final snapshot -> {args.state_out}")


if __name__ == "__main__":
    main()
