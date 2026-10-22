"use client";

import { motion } from "framer-motion";
import type { Stop } from "@/lib/types";

interface Props {
  stops: Stop[];
  selectedId: string | null;
  interactive: boolean;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
}

export default function StopList({ stops, selectedId, interactive, onSelect, onHover }: Props) {
  return (
    <ol className="-mx-2 space-y-0.5" aria-label="Duraklar">
      {stops.map((stop, i) => {
        const selected = interactive && stop.id === selectedId;
        return (
          <motion.li
            key={stop.id}
            initial={{ opacity: 0, x: -14 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08, duration: 0.35, ease: [0.2, 0.8, 0.2, 1] }}
          >
            <button
              type="button"
              disabled={!interactive}
              aria-pressed={selected}
              onClick={() => onSelect(stop.id)}
              onMouseEnter={() => interactive && onHover(stop.id)}
              onMouseLeave={() => interactive && onHover(null)}
              onFocus={() => interactive && onHover(stop.id)}
              onBlur={() => interactive && onHover(null)}
              className={`group grid w-full grid-cols-[44px_24px_1fr] items-start gap-2.5 rounded-xl px-2 py-2 text-left transition-colors disabled:cursor-default ${
                selected ? "bg-accent-soft" : "enabled:hover:bg-surface"
              }`}
            >
              <span className="tnum pt-[3px] font-mono text-[12px] text-muted">{stop.time}</span>
              <span
                className={`tnum grid size-6 place-items-center rounded-full font-mono text-[11px] font-bold transition-colors ${
                  selected ? "bg-accent text-white" : "bg-bubble text-bubble-text"
                }`}
              >
                {i + 1}
              </span>
              <span className="min-w-0">
                <span className="block text-[14.5px] leading-snug font-semibold">{stop.name}</span>
                {stop.tip && <span className="mt-0.5 block text-[13px] leading-snug text-muted">{stop.tip}</span>}
              </span>
            </button>
          </motion.li>
        );
      })}
    </ol>
  );
}
