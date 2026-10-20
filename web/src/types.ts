export type StatLine = { label: string; HOME: string; AWAY: string };

export type Audience = {
  type: "analyst" | "casual";
  club: string | null;
  player: string | null;
  lang: string;
};

export type TraceEntry = {
  seq: number;
  t: number;
  handoff: string;
  agent: string;
  action: string;
  status: "ok" | "retry" | "error" | "fallback";
  attempt: number;
  detail?: string;
};

export type Packet = {
  moment_id: string;
  t: number;
  clock: string;
  kind: string;
  priority: number;
  lang: string;
  headline: string;
  story: string;
  stat_lines: StatLine[];
  team: "HOME" | "AWAY" | null;
  scoreline: string;
  overlay: { duration_s: number; style: string; timed_for_overlay: boolean };
  focus: { kind: string; through: string | null };
  trace: Record<string, unknown>;
  audience: Audience;
};

export type TeamInfo = { name: string; color: string };

export type FullState = unknown;

export type Dataset = {
  meta: {
    seed: number;
    generated_by: string;
    narrator_mode: "llm" | "template";
    chaos: number;
    teams: { HOME: TeamInfo; AWAY: TeamInfo };
  };
  match_end_t: number;
  moments: Moment[];
  trace: TraceEntry[];
  full_state: FullState;
};

export type Moment = {
  id: string;
  t: number;
  clock: string;
  kind: string;
  priority: number;
  variants: Record<string, Packet>;
};
