"use client";

import { AnimatePresence, animate, motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { formatCoords, interestsLabel } from "@/lib/format";
import type { Mode, Trip } from "@/lib/types";

function CountUp({ value, decimals = 0 }: { value: number; decimals?: number }) {
  const reduced = useReducedMotion();
  const [display, setDisplay] = useState(0);
  const from = useRef(0);

  useEffect(() => {
    if (reduced) {
      setDisplay(value);
      from.current = value;
      return;
    }
    const controls = animate(from.current, value, {
      duration: 1.1,
      ease: [0.2, 0.8, 0.2, 1],
      onUpdate: (v) => setDisplay(v),
    });
    from.current = value;
    return () => controls.stop();
  }, [value, reduced]);

  return <>{display.toLocaleString("tr-TR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}</>;
}

function Stat({ label, value, decimals, unit }: { label: string; value: number; decimals?: number; unit?: string }) {
  return (
    <div className="min-w-[52px]">
      <div className="text-[10.5px] font-medium tracking-[0.08em] text-muted uppercase">{label}</div>
      <div className="tnum mt-0.5 font-mono text-[20px] leading-none font-semibold">
        <CountUp value={value} decimals={decimals} />
        {unit && <span className="ml-0.5 text-[12px] font-normal text-muted">{unit}</span>}
      </div>
    </div>
  );
}

function ModeToggle({ value, disabled, onChange }: { value: Mode; disabled: boolean; onChange: (m: Mode) => void }) {
  const options: { value: Mode; label: string }[] = [
    { value: "yuruyus", label: "Yürüyüş" },
    { value: "arac", label: "Araç" },
  ];
  return (
    <div role="radiogroup" aria-label="Ulaşım şekli" className="relative flex rounded-full border border-line bg-surface p-[3px]">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={disabled}
            onClick={() => onChange(o.value)}
            className={`relative rounded-full px-3 py-1.5 text-[12.5px] font-semibold transition-colors disabled:cursor-wait ${
              active ? "text-text" : "text-muted hover:text-text"
            }`}
          >
            {active && (
              <motion.span
                layoutId="mode-pill"
                className="absolute inset-0 rounded-full border border-line bg-panel shadow-sm"
                transition={{ type: "spring", stiffness: 420, damping: 34 }}
              />
            )}
            <span className="relative">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}

interface Props {
  trip: Trip | null;
  busy: boolean;
  onMode: (m: Mode) => void;
}

export default function MapHeader({ trip, busy, onMode }: Props) {
  const [lon, lat] = trip?.center ?? [0, 0];
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3 border-b border-line px-4 py-3.5 min-[820px]:px-5 min-[820px]:py-4">
      <div className="min-w-0">
        <AnimatePresence mode="wait" initial={false}>
          <motion.h1
            key={trip?.city ?? "—"}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.3 }}
            className="font-display text-[clamp(28px,3.3vw,40px)] leading-[0.95] font-extrabold tracking-[-0.045em]"
          >
            {trip?.city ?? "Rota"}
          </motion.h1>
        </AnimatePresence>
        {trip && (
          <p className="tnum mt-2 truncate font-mono text-[11.5px] text-muted">
            {formatCoords(lat, lon)} · {interestsLabel(trip.intent.ilgi)}
          </p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
        <div className="flex gap-4">
          <Stat label="Durak" value={trip?.stops.length ?? 0} />
          <Stat label="Km" value={trip?.route.distance_km ?? 0} decimals={1} />
          <Stat label="Süre" value={Math.round(trip?.route.duration_min ?? 0)} unit="dk" />
        </div>
        <ModeToggle value={trip?.route.mode ?? "yuruyus"} disabled={busy || !trip} onChange={onMode} />
      </div>
    </div>
  );
}
