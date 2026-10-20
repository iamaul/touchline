# SecondSight — 7-Day Build Plan

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
- [ ] Stats engine: rolling possession, momentum, pressure index, pass difficulty, xT
- [ ] MatchState schema + snapshot/export
- [ ] End-to-end: simulator → interpreter → stats visible on a console/debug page

### Day 3
- [ ] Moment scoring (momentum swings, goal threat, control vs. chaos)
- [ ] Explainer agent grounded in MatchState (no hallucination: cite state)
- [ ] Moment log persistence

### Day 4
- [ ] Narrator agent: structured packet schema `{t, headline, story, statLines[], lang}`
- [ ] Multi-language output (Foundry model)
- [ ] Personalizer: profiles (analyst/casual/club/player/language)
- [ ] Orchestrator: handoffs, retry, agent trace

### Day 5
- [ ] Overlay preview with synchronized timing
- [ ] Dashboard + persona flip + language switch
- [ ] Insurance demo recording

### Day 6
- [ ] Azure Functions ingestion (Event Hubs), behind config flag
- [ ] azd project wiring
- [ ] Docs, README polish, license header

### Day 7
- [ ] Record final video (<2 min), upload (YouTube unlisted OK)
- [ ] Pitch/ elevator text
- [ ] Submission form on hackathon platform
- [ ] Final compliance checklist pass
