# Touchline — 7-Day Build Plan

Solo entry · ~20h budget · Deadline: **Oct 27, 2026 11:59 PM PT** · Today: Oct 20

## Milestones

| Day | Date | Goal | Deliverables |
|---|---|---|---|
| 1 | Mon Oct 20 | Scaffold + data | Repo skeleton, simulator emitting football-realistic event stream (seeded, accelerated replay) |
| 2 | Tue Oct 21 | Stats brain | Stats engine (possession, momentum, pressure, pass difficulty, xT), shared MatchState, simulator→agent loop |
| 3 | Wed Oct 22 | Explain | Interpreter + Moment-Explainer agents, moment detection & causal explanations |
| 4 | Thu Oct 23 | Narrate + personalize | Narrator agent (multi-language), Personalizer agent, orchestrator w/ handoffs + failure recovery |
| 5 | Fri Oct 24 | UI | Next.js: overlay preview, analyst dashboard, persona flip (fan mode) |
| 6 | Sat Oct 25 | Azure + polish | Functions ingestion path, azd wiring, docs, README, agent trace UI |
| 7 | Sun Oct 26 | Submit-ready | Demo video (<2 min) storyboard + record, pitch text, compliance checklist, buffer |

> Submission form + video should be done **a day early** — don't leave the video to deadline night.

## Working rules

- Demo mode must always work locally with zero Azure dependencies.
- Every commit keeps the demo runnable.
- Record the demo video at least twice: once mid-build (Day 5) as insurance, once polished (Day 6).

## Daily checklists

### Day 1 — today
- [x] Repo scaffold + docs
- [x] Simulator: event types, seeded randomness, pitch coordinates
- [x] Simulator: replay-speed control + JSONL output

### Day 2
- [x] Stats engine: rolling possession, momentum, pressure index, pass difficulty, xT
- [x] MatchState schema + snapshot/export (`--json-out`, `--state-out`)
- [x] End-to-end: simulator → engine → console debug view (`python -m agents.run_debug`)


### Day 3
- [x] Moment scoring (momentum swings, goal threat, control vs. chaos)
- [x] Explainer grounded in MatchState (no hallucination: every claim cites data)
- [x] Moment log persistence (`--moments-out` JSONL)


### Day 4
- [x] Narrator agent: structured packet schema `{t, headline, story, statLines[], lang}` + overlay timing hints
- [x] Multi-language output (Foundry/GitHub-Models-compatible LLM adapter; deterministic template fallback with zero keys)
- [x] Personalizer: profiles (analyst/casual/club/player/language) with grounded focus lens
- [x] Orchestrator: handoffs, retry + backoff, graceful fallbacks, injectable chaos demo, JSONL agent trace

### Day 5
- [x] Overlay preview with synchronized timing (React + Vite + TS + Tailwind; replay clock with speed control + ON-AIR window per overlay.duration_s) — **visually verified** (screenshot: score/header/feed/trace live)
- [x] Dashboard + persona flip + language switch (analyst/casual, EN/ES; agent-trace panel with retry/fallback highlighting)
- [ ] Demo recording (Day 7)

### Day 6
- [ ] Azure Functions ingestion (Event Hubs), behind config flag
- [ ] azd project wiring
- [ ] Docs, README polish, license header

### Day 7
- [ ] Record final video (<2 min), upload (YouTube unlisted OK)
- [ ] Pitch/ elevator text
- [ ] Submission form on hackathon platform
- [ ] Final compliance checklist pass
