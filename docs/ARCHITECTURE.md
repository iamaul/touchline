# SecondSight — Architecture

## Overview

SecondSight is a real-time, explainable match-intelligence system built around a
multi-agent pipeline. It is designed to run in two modes:

1. **Local demo mode** (default for judging) — simulator → local agent loop → local API → web UI.
   Zero cloud dependencies, zero cost, fully reproducible.
2. **Azure-native mode** — the same pipeline with the ingestion path swapped to
   Azure Functions + Event Hubs and state in Cosmos DB. Wired for `azd up`.

## Components

### 1. Synthetic Event Simulator (`simulator/`)
The rules require synthetic, football-realistic data and prohibit redistribution of real
match data, so we generate our own. The simulator emits a realistic event stream:

- Event types: pass, shot, tackle, foul, interception, possession change, pressure event,
  goal, card, substitution, corner, plus match metadata (clock, score).
- **Space-aware**: events carry pitch coordinates so we can derive meaningful geometry
  (pass distance, field tilt, zone occupancy) rather than flat counts.
- **Football-literacy**: a lightweight pitch-control model influences where the next event
  happens, so the stream exhibits genuine runs, collapses, and pressure waves —
  giving the Explainer agent real "why" signal instead of noise.
- **Replay control**: matches can be accelerated (e.g., full match in 60s) for demos and tests.
- Output: JSON lines over a queue, deterministic given a seed (for demos & tests).

### 2. Ingestion (`gateway/`, Azure Functions)
- Local mode: direct in-process consumption of the event stream.
- Azure mode: an isolated Azure Function consuming from Event Hubs / queue trigger,
  normalizing events into the shared schema before agent consumption.

### 3. Multi-agent pipeline (`agents/`, Microsoft Agent Framework)

```
EventStream ──▶ Interpreter ──▶ MatchState (shared) ──▶ Moment-Explainer
                                                       │   key moment candidates
                                                       ▼
                                              Narrator ──▶ Personalizer ──▶ Output bus
```

- **Shared state**: `MatchState` (rolling stats, current momentum, pressure map, recent
  narratives) is the single source of truth all agents read/write through the orchestrator.
- **Interpreter Agent**: deterministic aggregation + LLM-assisted labeling. Emits updated
  MatchState deltas every tick.
- **Moment-Explainer Agent**: scores event windows against momentum/pressure/threat models,
  selects key moments, produces *causal* explanations citing the computed state.
- **Narrator Agent**: renders explanation → structured narrative packet:
  `{ t: matchClock, momentId, headline, story, statLines[], langDefault }`.
- **Personalizer Agent**: takes narrator output + viewer profile → retargeted packet
  (analyst: dense numbers; casual: plain-language hook; fan mode: club/player framing
  and target language).
- **Orchestrator**: routes calls, maintains handoffs, retries failed renderings,
  and exposes the agent trace — which doubles as demo material.

### 4. Output & serving (`gateway/` → WebSockets/SSE)
Narrative packets are pushed to clients as:
- **Overlay packets**: `t` (match clock), duration, priority, machine-readable JSON —
  designed to be dropped into a graphics renderer beside a live feed.
- **Dashboard data**: rolling stats and momentum series for the analyst view.

### 5. Web UI (`web/`, Next.js)
- **Overlay preview**: a mock "match view" with synchronized overlay cards, showing
  timestamped narratives appearing as moments happen.
- **Analyst dashboard**: live stats, momentum chart, pressure map, moment log.
- **Fan mode**: same moment, personalized rendering — persona switcher
  (analyst ↔ casual fan), favorite club/player selector, language selector.
- The persona flip is a one-click, on-camera demonstration of the personalization stage.

## Data flow guarantees

- Every narrative packet is traceable to the events that caused it (moment → events list),
  supporting "explainability" and easy debugging.
- The agent trace (which agent did what, passed what) is persisted and visible in the UI.

## Security & reliability notes (enterprise realism)

- Schema validation at ingestion; dead-letter on malformed events.
- Idempotent event consumption.
- Retry policy on agent rendering; graceful degradation (stats still flow if the
  narrative agent is down, explainer falls back to deterministic templates).
