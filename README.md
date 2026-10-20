# Touchline

**Explainable match intelligence, narrated live by a team of AI agents.**

Touchline ingests synthetic football match events in real time and runs a multi-agent
pipeline that turns raw events into meaningful statistics, explains *why* key moments
matter, renders them as overlay-ready broadcast narratives, and personalizes them
for analysts and fans alike.

> Entry for **Inside the Game: Developer Hackathon** (Microsoft × Premier League), October 2026.
> Category target: **Best Multi-Agent System**.

---

## The pipeline

```
Synthetic Event Simulator          (Data innovation — football-realistic synthetic events)
        │  event stream (passes, shots, tackles, possession, pressure, metadata)
        ▼
┌────────────────────────────────────────────────────────────────┐
│                     Agent Orchestrator                         │
│   shared state · handoffs · failure recovery                   │
│                                                                │
│   ┌──────────────┐  ┌────────────────┐  ┌──────────────────┐    │
│   │  Interpreter │→│ Moment-Explainer │→│     Narrator     │    │
│   │    Agent     │  │      Agent       │  │      Agent       │    │
│   └──────────────┘  └────────────────┘  └──────────────────┘    │
│                                │                               │
│                       ┌────────▼─────────┐                      │
│                       │  Personalizer    │                      │
│                       │     Agent        │                      │
│                       └──────────────────┘                      │
└────────────────────────────────────────────────────────────────┘
        │  timed, machine-readable narrative packets
        ▼
Broadcast overlay view · Analyst dashboard · Personalized fan view
```

| Stage | Component | What it does |
|---|---|---|
| **Ingest** | `simulator/` → `gateway/` | Streams synthetic match events as they happen |
| **Interpret** | Interpreter Agent | Live possession %, momentum, pressure index, pass difficulty, xT |
| **Explain** | Moment-Explainer Agent | Why a moment matters: control vs. chaos, momentum swings, tactical shifts |
| **Render** | Narrator Agent + web overlay | Broadcast-grade copy, timestamped and machine-readable for synchronized overlays |
| **Personalize** | Personalizer Agent | Same moment, genuinely different experiences: analyst ↔ casual fan, club/player focus, language |

## Multi-agent design

Four specialized agents coordinate through an orchestrator:

- **Interpreter Agent** — pure computation-first: aggregates events into rolling match state
  and football-derived metrics.
- **Moment-Explainer Agent** — curates: detects moments worth narrating and produces causal
  explanations grounded in the computed state (never invents).
- **Narrator Agent** — renders: converts explanations into structured narrative packets
  (headline, story, stats — with match-clock timestamp, multi-language ready).
- **Personalizer Agent** — adapts: re-renders each packet per viewer profile
  (analyst / casual fan / favorite club / favorite player / language preference).

Each agent has a distinct role, coordinates through shared match state, hands off explicitly,
and the orchestrator handles failure recovery (e.g., re-requesting an explanation if rendering fails).

## Repository layout

```
simulator/   Synthetic football match event simulator (Python)
gateway/     Event ingestion path (Azure Functions wiring)
agents/      Multi-agent pipeline (Microsoft Agent Framework)
web/         Overlay UI, analyst dashboard, fan mode (Next.js)
docs/        Architecture, plan, demo script
```

## Running (MVP — local first)

Everything runs locally without an Azure account for judging/testing; the Azure-native
ingestion and deployment paths are wired and `azd`-ready. See `docs/`.

---

## Hackathon compliance checklist

- [ ] Synthetic, football-realistic data only (no real match footage) — own simulator
- [ ] Five-stage pipeline: ingest → interpret → explain → render → personalize
- [ ] Multi-language narrative output
- [ ] Overlay-ready: timed + machine-readable outputs
- [ ] Two distinct experiences: analyst vs. casual fan
- [ ] Public GitHub repo, demo video < 2 min (English), live-testable demo
- [ ] Hero technologies: Microsoft Agent Framework, Azure AI Foundry, Azure Functions, GitHub Copilot
