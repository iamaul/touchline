import { useEffect, useMemo, useState } from "react";
import { Header, Controls, PersonaBar, MomentCard, Feed, TracePanel } from "@/components/panels";
import { useClock } from "@/lib/useClock";
import type { Dataset } from "@/types";
import { cx } from "@/lib/cx";

type Persona = "analyst" | "casual";
type Lang = "en" | "spanish";

export default function App() {
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [persona, setPersona] = useState<Persona>("casual");
  const [lang, setLang] = useState<Lang>("en");

  useEffect(() => {
    fetch("/data.json")
      .then((r) => {
        if (!r.ok) throw new Error(`data.json ${r.status}`);
        return r.json() as Promise<Dataset>;
      })
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);

  const play = useClock(data?.match_end_t ?? 5400);
  if (error || !data) {
    return (
      <div className="grid h-full place-items-center">
        <div className="max-w-md text-center text-sm text-zinc-400">
          <p className="text-lg font-bold text-zinc-200">Touchline</p>
          {error ? (
            <p className="mt-2">{error}</p>
          ) : (
            <p className="mt-2">loading match intelligence…</p>
          )}
          {error && (
            <p className="mt-3 text-xs text-zinc-500">
              generate a dataset first:
              <code className="mx-1 rounded bg-zinc-900 px-1.5 py-0.5">
                python3 -m agents.run_pipeline --web-out web/public
              </code>
            </p>
          )}
        </div>
      </div>
    );
  }

  const variantKey = `${persona}|${lang === "en" ? "en" : "spanish"}`;
  const currentIdx = useMemo(() => {
    let idx = -1;
    for (let i = 0; i < data.moments.length; i++) {
      if (data.moments[i].t <= play.t) idx = i;
      else break;
    }
    return idx;
  }, [data, play.t]);

  const onAir = currentIdx >= 0 ? data.moments[currentIdx] : null;
  const variant = onAir
    ? onAir.variants[variantKey] ?? Object.values(onAir.variants)[0]
    : null;

  // ON AIR window: real-time overlay duration per priority
  const [airUntil, setAirUntil] = useState(0);
  useEffect(() => {
    if (variant) {
      setAirUntil(Date.now() + variant.overlay.duration_s * 1000);
      const timer = setTimeout(() => setAirUntil(0), variant.overlay.duration_s * 1000);
      return () => clearTimeout(timer);
    }
  }, [variant?.moment_id, variant?.lang]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex min-h-dvh flex-col">
      <Header data={data} t={play.t} />

      <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-950/60">
        <Controls playback={play} endT={data.match_end_t} />
        <div className="px-6">
          <PersonaBar persona={persona} lang={lang} onPersona={setPersona} onLang={setLang} />
        </div>
      </div>

      <main className="mx-auto grid w-full max-w-7xl flex-1 grid-cols-[1.7fr_1fr] gap-5 p-6">
        {/* left: live moment + feed */}
        <section className="flex min-h-0 flex-col gap-4">
          {variant ? (
            <MomentCard p={variant} live={Date.now() < airUntil} />
          ) : (
            <div className="rounded-xl border border-dashed border-zinc-800 p-8 text-center text-sm text-zinc-500">
              the moment feed lights as the match unfolds — press play
            </div>
          )}

          <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500">
            moment feed
            <span className="text-zinc-600">{data.moments.length} total</span>
          </div>
          <Feed data={data} t={play.t} variantKey={variantKey} onJump={play.jumpTo} />
        </section>

        {/* right: multi-agent system panel */}
        <section className="flex min-h-0 flex-col gap-4">
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="flex items-baseline justify-between">
              <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">
                system
              </span>
              <span className="text-[10px] text-zinc-600">seed {data.meta.seed}</span>
            </div>
            <p className="mt-1 text-xs leading-relaxed text-zinc-400">
              4 agents over 1 shared state. handoffs, retries & fallbacks are logged live —
              everything you see is grounded in MatchState.
            </p>
          </div>
          <div className="min-h-0 flex-1 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
            <TracePanel data={data} t={play.t} />
          </div>
        </section>
      </main>
    </div>
  );
}
