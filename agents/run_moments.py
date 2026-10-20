"""Day 3 end-to-end: sim -> StatsEngine -> MomentDetector -> ExplainerAgent.

    python -m agents.run_moments                       # default match
    python -m agents.run_moments --seed 7 --speed 300  # fast-forward
    python -m agents.run_moments --moments-out moments.jsonl
"""

from __future__ import annotations

import argparse
import json

from agents import MatchState, StatsEngine
from agents.explainer import ExplainerAgent
from agents.moments import MomentDetector
from agents.state import event_clock
from simulator import Event, MatchSimulator, default_teams


def render(expl: dict) -> str:
    priority_tag = {1: "P1", 2: "P2", 3: "P3"}.get(expl["priority"], "P?")
    lines = [
        f"  [{priority_tag}] {expl['clock']}  {expl['headline']}",
        f"         why: {expl['why']}",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Touchline moment feed (Day 3)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--speed", type=float, default=300.0)
    ap.add_argument("--moments-out", default=None, help="append explanations to JSONL")
    ap.add_argument("--final-state-out", default=None)
    args = ap.parse_args()

    home, away = default_teams(args.seed)
    state = MatchState(home, away, seed=args.seed)
    engine = StatsEngine(state)
    detector = MomentDetector()
    explainer = ExplainerAgent()

    log = open(args.moments_out, "a") if args.moments_out else None
    counts: dict[str, int] = {}

    print(f"Touchline moment feed | seed {args.seed} | "
          f"{state.team_name('HOME')} vs {state.team_name('AWAY')}\n" + "─" * 62)

    for ev in MatchSimulator(seed=args.seed, speed=args.speed).run():
        engine.update(ev)
        moment = detector.detect(ev, state)
        if not moment:
            continue
        expl = explainer.explain(moment, state)
        print(render(expl), flush=True)
        counts[expl["kind"]] = counts.get(expl["kind"], 0) + 1
        if log:
            log.write(json.dumps(expl, ensure_ascii=False) + "\n")
            log.flush()

    if log:
        log.close()

    print("─" * 62)
    print(f"  Moments detected: {sum(counts.values())}  {json.dumps(counts)}")
    print(f"  Final score {state.score['HOME']}-{state.score['AWAY']}  |  "
          f"xG {[round(state.shots[team]['xg_sum'], 2) for team in ('HOME', 'AWAY')]}")
    if args.final_state_out:
        with open(args.final_state_out, "w") as f:
            json.dump(state.snapshot(), f, indent=2)


if __name__ == "__main__":
    main()
