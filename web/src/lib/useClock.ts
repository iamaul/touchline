import { useEffect, useRef, useState } from "react";

const TICK_MS = 100;

export type Playback = {
  t: number;
  playing: boolean;
  speed: number;
  setSpeed: (s: number) => void;
  toggle: () => void;
  jumpTo: (t: number) => void;
  restart: () => void;
};

export function useClock(endT: number): Playback {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(60); // match-seconds per real second
  const raf = useRef<number | null>(null);
  const last = useRef<number>(0);

  useEffect(() => {
    if (!playing) return;
    last.current = performance.now();
    const step = (now: number) => {
      const dt = (now - last.current) / 1000;
      last.current = now;
      setT((prev) => {
        const next = prev + dt * speed;
        if (next >= endT) {
          setPlaying(false);
          return endT;
        }
        return next;
      });
      raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => {
      if (raf.current !== null) cancelAnimationFrame(raf.current);
    };
  }, [playing, speed, endT]);

  return {
    t,
    playing,
    speed,
    setSpeed,
    toggle: () => setPlaying((p) => !p),
    jumpTo: (target: number) => setT(Math.min(Math.max(0, target), endT - 0.01)),
    restart: () => {
      setT(0);
      setPlaying(true);
    },
  };
}
