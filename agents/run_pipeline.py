"""Full agent pipeline demo — the Day 4 deliverable.

    python -m agents.run_pipeline                              # normal run
    python -m agents.run_pipeline --seed 7 --chaos 0.15        # failure recovery demo
    python -m agents.run_pipeline --fav-player "Pedro Mbeki" --fav-club "Northgate FC"
    python -m agents.run_pipeline --packets-out packets.jsonl --trace-out trace.jsonl

Default audience set: analyst (English) + casual (English) + casual (Spanish
translation via LLM when a provider is configured; template fallback otherwise).

LLM (optional, zero-dep fallback):
    TOUCHLINE_LLM_BASE_URL / TOUCHLINE_LLM_API_KEY / TOUCHLINE_LLM_MODEL
    or GITHUB_TOKEN (GitHub Models endpoint)
"""

from __future__ import annotations

import argparse
import json

from agents import MatchState
from agents.orchestrator import Orchestrator
from agents.llm import detect_config
from agents.personalizer import ViewerProfile
from agents.state import event_clock
from simulator import default_teams, MatchSimulator


def render_packet(p: dict) -> str:
    aud = p["audience"]
    tag = f"{aud['type']}/{aud['lang']}"
    lines = [
        f"    [{tag}] [{p['focus']['kind']}] {p['clock']}  {p['headline']}",
        f"            {p['story']}",
        f"            chips: {', '.join(s['label'] + ' ' + (s['HOME'] if s['HOME'] != '' else '') for s in p['stat_lines']) or '—'}",
        f"            narrator={p['trace'].get('narrator', '?')} personalizer={p['trace'].get('personalizer', '?')}",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Touchline agent pipeline (Day 4)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--speed", type=float, default=1e9)
    ap.add_argument("--chaos", type=float, default=0.0,
                    help="probability of injected agent failure (0..1) — recovery demo")
    ap.add_argument("--fav-club", default=None)
    ap.add_argument("--fav-player", default=None)
    ap.add_argument("--casual-lang", default="Spanish",
                    help="second language for the casual profile ('' to disable)")
    ap.add_argument("--packets-out", default=None)
    ap.add_argument("--trace-out", default=None)
    args = ap.parse_args()

    chat_cfg = detect_config()
    profiles = [
        ViewerProfile("analyst", lang="en"),
        ViewerProfile("casual", club=args.fav_club, player=args.fav_player, lang="en"),
    ]
    if args.casual_lang:
        profiles.append(ViewerProfile("casual", club=args.fav_club,
                                      player=args.fav_player, lang=args.casual_lang))

    home, away = default_teams(args.seed)
    state = MatchState(home, away, seed=args.seed)
    orch = Orchestrator(state, profiles, chat_cfg=chat_cfg, chaos_prob=args.chaos,
                        seed=args.seed)

    packets_f = open(args.packets_out, "a") if args.packets_out else None
    mode = "LLM" if chat_cfg else "template (no LLM configured)"
    chaos = f" chaos={args.chaos}" if args.chaos else ""

    print(f"Touchline pipeline | seed {args.seed} | "
          f"{state.team_name('HOME')} vs {state.team_name('AWAY')} | narrator mode: {mode}{chaos}")
    print("─" * 70)

    for ev in MatchSimulator(seed=args.seed, speed=args.speed).run():
        packets = orch.process_event(ev)
        if not packets:
            continue
        first = packets[0]
        aud0 = first["audience"]
        print(f"  [{first['clock']}] {first['kind']} "
              f"({first['priority']}) — shown to {len(packets)} audiences:\n")
        for p in packets:
            print(render_packet(p), end="")
        if packets_f:
            for p in packets:
                packets_f.write(json.dumps(p, ensure_ascii=False) + "\n")
            packets_f.flush()

    if packets_f:
        packets_f.close()
    if args.trace_out:
        with open(args.trace_out, "w") as f:
            f.write(orch.trace.to_jsonl() + "\n")

    print("─" * 70)
    s = orch.stats
    print(f"  moments={s['moments']}  packets={s['packets']}  "
          f"retries={s['retries']}  fallbacks={s['fallbacks']}")
    print(f"  final score {state.score['HOME']}-{state.score['AWAY']}  |  "
          f"trace entries={orch.trace.seq}")


if __name__ == "__main__":
    main()
