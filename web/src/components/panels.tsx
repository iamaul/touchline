import { cx } from "@/lib/cx";
import { clockFmt } from "@/lib/fmt";
import type { Dataset } from "@/types";

export function Header({ data, t }: { data: Dataset; t: number }) {
  const { teams } = data.meta;
  const goals = data.moments
    .filter((m) => m.t <= t && m.kind === "GOAL")
    .map((m) => Object.values(m.variants)[0])
    .filter((p) => p.scoreline);
  const score = goals.length ? goals[goals.length - 1].scoreline : "0-0";
  const fullTime = t >= data.match_end_t - 0.01;

  return (
    <header className="flex items-center gap-4 border-b border-zinc-800 px-6 py-4">
      <div className="flex items-center gap-2">
        <span className="text-xl font-black tracking-tight text-emerald-400">TOUCHLINE</span>
        <span className="rounded bg-zinc-800 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
          match intelligence
        </span>
      </div>

      <div className="mx-auto flex items-center gap-4">
        <span className="flex items-center gap-2 text-sm font-bold" style={{ color: teams.HOME.color }}>
          {teams.HOME.name}
        </span>
        <span className="tnum rounded-lg bg-zinc-900 px-4 py-1.5 text-2xl font-black ring-1 ring-zinc-800">
          {score}
        </span>
        <span className="flex items-center gap-2 text-sm font-bold" style={{ color: teams.AWAY.color }}>
          {teams.AWAY.name}
        </span>
      </div>

      <div className="flex items-center gap-3">
        {!fullTime ? (
          <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-rose-400">
            <span className="live-dot inline-block h-2 w-2 rounded-full bg-rose-500" /> live
          </span>
        ) : (
          <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs font-semibold uppercase tracking-widest text-zinc-300">
            full time
          </span>
        )}
        <span className="tnum rounded bg-zinc-900 px-3 py-1 text-lg font-bold ring-1 ring-zinc-800">
          {clockFmt(Math.min(t, data.match_end_t))}
        </span>
      </div>
    </header>
  );
}

export function Controls({ playback, endT }: { playback: { playing: boolean; speed: number; toggle: () => void; restart: () => void; setSpeed: (n: number) => void; t: number }; endT: number }) {
  const speeds = [15, 60, 240];
  return (
    <div className="flex items-center gap-2 px-6 py-3">
      <button
        onClick={playback.toggle}
        className="rounded-md bg-emerald-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-40"
        disabled={playback.t >= endT - 0.01 && !playback.playing}
      >
        {playback.playing ? "⏸ Pause" : "▶ Play"}
      </button>
      {speeds.map((s) => (
        <button
          key={s}
          onClick={() => playback.setSpeed(s)}
          className={cx(
            "rounded-md px-3 py-1.5 text-xs font-semibold ring-1",
            playback.speed === s
              ? "bg-zinc-100 text-zinc-900 ring-zinc-100"
              : "bg-transparent text-zinc-400 ring-zinc-700 hover:text-zinc-200"
          )}
        >
          {s}×
        </button>
      ))}
      <button onClick={playback.restart} className="ml-2 text-xs text-zinc-500 hover:text-zinc-300">
        ⟲ restart
      </button>
    </div>
  );
}

export function PersonaBar({
  persona,
  lang,
  onPersona,
  onLang,
}: {
  persona: "analyst" | "casual";
  lang: "en" | "spanish";
  onPersona: (p: "analyst" | "casual") => void;
  onLang: (l: "en" | "spanish") => void;
}) {
  const seg = (
    value: string,
    options: Array<[string, string]>,
    onSelect: (v: string) => void,
  ) => (
    <div className="inline-flex rounded-lg bg-zinc-900 p-1 ring-1 ring-zinc-800">
      {options.map(([key, label]) => (
        <button
          key={key}
          onClick={() => onSelect(key)}
          className={cx(
            "rounded-md px-3 py-1 text-xs font-semibold transition",
            value === key ? "bg-zinc-200 text-zinc-900" : "text-zinc-400 hover:text-zinc-200"
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
  return (
    <div className="flex items-center gap-4">
      <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">audience</span>
      {seg(persona, [["analyst", "📊 Analyst"], ["casual", "🍿 Casual fan"]], onPersona)}
      <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">language</span>
      {seg(lang, [["en", "EN"], ["spanish", "ES"]], onLang)}
    </div>
  );
}

const KIND_TINT: Record<string, string> = {
  GOAL: "border-emerald-500/60 bg-emerald-500/10",
  BIG_CHANCE: "border-amber-500/50 bg-amber-500/10",
  END_TO_END: "border-fuchsia-500/50 bg-fuchsia-500/10",
  MOMENTUM_SWING: "border-sky-500/50 bg-sky-500/10",
  PRESSURE_SURGE: "border-orange-500/50 bg-orange-500/10",
};

export function MomentCard({ p, live }: { p: PacketLike; live: boolean }) {
  return (
    <article
      className={cx(
        "rounded-xl border-l-4 p-5 shadow-lg transition",
        KIND_TINT[p.kind] ?? "border-zinc-600 bg-zinc-900",
        live && "ring-2 ring-rose-500/80"
      )}
    >
      <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-zinc-400">
        <span className="tnum">{p.clock}</span>
        <span className="rounded bg-zinc-800 px-1.5 py-0.5">{p.kind.replace(/_/g, " ")}</span>
        <span className="rounded bg-zinc-800 px-1.5 py-0.5">P{p.priority}</span>
        {p.focus.kind !== "match" && (
          <span className="rounded bg-indigo-500/20 px-1.5 py-0.5 text-indigo-300">
            {p.focus.kind.replace(/-/g, " ")}
          </span>
        )}
        {live && (
          <span className="ml-auto rounded bg-rose-600 px-1.5 py-0.5 text-white">ON AIR</span>
        )}
      </div>
      <h2 className="mt-2 text-xl font-extrabold leading-snug text-zinc-50">{p.headline}</h2>
      <p className="mt-1.5 text-sm leading-relaxed text-zinc-300">{p.story}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {p.stat_lines.map((s, i) => (
          <span key={i} className="rounded-md bg-zinc-950/70 px-2 py-1 text-[11px] ring-1 ring-zinc-800">
            <span className="text-zinc-500">{s.label}</span>{" "}
            <span className="tnum font-bold text-zinc-100">
              {s.HOME || "—"}
              {s.AWAY ? <span className="tnum font-bold text-zinc-100"> / {s.AWAY}</span> : null}
            </span>
          </span>
        ))}
      </div>
      <div className="mt-3 flex gap-2 text-[10px] font-semibold uppercase tracking-wide">
        {Object.entries(p.trace).map(([k, v]) => (
          <span
            key={k}
            className={cx(
              "rounded px-1.5 py-0.5",
              v === "llm" ? "bg-sky-500/15 text-sky-300" : "bg-zinc-800 text-zinc-400",
              v === "fallback" && "bg-rose-500/15 text-rose-300"
            )}
          >
            {k}: {String(v)}
          </span>
        ))}
      </div>
    </article>
  );
}

type PacketLike = {
  kind: string;
  clock: string;
  priority: number;
  headline: string;
  story: string;
  stat_lines: Array<{ label: string; HOME: string; AWAY: string }>;
  focus: { kind: string; through: string | null };
  trace: Record<string, unknown>;
};

export function Feed({
  data,
  t,
  variantKey,
  onJump,
}: {
  data: Dataset;
  t: number;
  variantKey: string;
  onJump: (t: number) => void;
}) {
  const seen = data.moments.filter((m) => m.t <= t);
  return (
    <div className="flex flex-col gap-2 overflow-y-auto pr-1">
      {[...seen].reverse().map((m) => {
        const p = m.variants[variantKey] ?? Object.values(m.variants)[0];
        return (
          <button
            key={m.id}
            onClick={() => onJump(m.t - 0.001)}
            className="w-full rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-left transition hover:border-zinc-600"
          >
            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-zinc-500">
              <span className="tnum">{m.clock}</span>
              <span className="rounded bg-zinc-800 px-1.5">{m.kind.replace(/_/g, " ")}</span>
            </div>
            <div className="mt-0.5 truncate text-sm font-semibold text-zinc-200">{p.headline}</div>
          </button>
        );
      })}
      {!seen.length && (
        <p className="px-2 py-6 text-center text-xs text-zinc-600">match starting…</p>
      )}
    </div>
  );
}

const STATUS_STYLE: Record<string, string> = {
  ok: "text-zinc-400",
  retry: "text-amber-300",
  error: "text-rose-400",
  fallback: "text-rose-300 bg-rose-500/10",
};

export function TracePanel({ data, t }: { data: Dataset; t: number }) {
  const entries = data.trace.filter((e) => e.t <= t).slice(-18).reverse();
  const recoveries = data.trace.filter((e) => e.t <= t && e.status === "fallback").length;
  const retries = data.trace.filter((e) => e.t <= t && e.status !== "ok" && e.status !== "fallback").length;
  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">agent trace</span>
        <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">
          {retries} retry
        </span>
        <span className="rounded bg-rose-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-rose-300">
          {recoveries} fallback
        </span>
      </div>
      <div className="flex flex-col gap-1 overflow-y-auto font-mono text-[10.5px] leading-relaxed">
        {entries.map((e) => (
          <div key={e.seq} className={cx("flex gap-2", STATUS_STYLE[e.status])}>
            <span className="tnum text-zinc-600">{e.seq}</span>
            <span className="tnum text-zinc-600">{clockFmt(e.t)}</span>
            <span className="text-zinc-300">{e.agent}</span>
            <span className="truncate text-zinc-500">{e.action}</span>
            <span className={cx("ml-auto font-bold", e.status !== "ok" && "font-bold")}>{e.status}</span>
          </div>
        ))}
        {!entries.length && (
          <p className="p-4 text-center text-zinc-600">waiting on first handoff…</p>
        )}
      </div>
    </div>
  );
}
