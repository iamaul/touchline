# Touchline web overlay

React + Vite + TypeScript + Tailwind (shadcn-flavoured components, no runtime
deps). Replays an orchestrator dataset as a "live" broadcast with a synced
match clock, persona flip (analyst / casual fan), language switch (EN / ES),
and a live agent-trace panel.

## Run

```bash
# 1. dataset (from repo root) — regenerates the replayable match
python3 -m agents.run_pipeline --seed 42 --speed 1e9 --web-out web/public

# (optional) failure-recovery.dataset for the trace demo
python3 -m agents.run_pipeline --seed 42 --speed 1e9 --chaos 0.2 --web-out web/public

# 2. web app
bun install
bun run dev     # http://localhost:5173
bun run build   # production bundle (data.json is copied from public/)
```

## Data contract

`web/public/data.json` — written by `agents.run_pipeline --web-out web/public`,
schema in `src/types.ts` (`Dataset`). The UI never generates facts; it only
replays what the agents produced.
