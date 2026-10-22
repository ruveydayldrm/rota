"use client";

import { AnimatePresence, motion } from "framer-motion";
import dynamic from "next/dynamic";
import type { ResolvedTheme } from "@/lib/mapStyle";
import type { Mode, Trip } from "@/lib/types";
import InfoCard from "./InfoCard";
import MapHeader from "./MapHeader";

const MapView = dynamic(() => import("./MapView"), {
  ssr: false,
  loading: () => <div className="absolute inset-0 animate-pulse bg-water/30" />,
});

interface Props {
  className?: string;
  trip: Trip | null;
  theme: ResolvedTheme;
  animKey: number;
  busy: boolean;
  rerouting: boolean;
  notice: string | null;
  selectedId: string | null;
  hoveredId: string | null;
  reducedMotion: boolean;
  onSelect: (id: string | null) => void;
  onMode: (m: Mode) => void;
  onDismissNotice: () => void;
}

export default function MapPanel(props: Props) {
  const { className = "", trip, selectedId, notice } = props;
  const index = trip?.stops.findIndex((s) => s.id === selectedId) ?? -1;
  const selected = index >= 0 && trip ? trip.stops[index] : null;

  return (
    <section aria-label="Harita" className={`panel flex min-h-0 flex-col overflow-hidden ${className}`}>
      <MapHeader trip={trip} busy={props.busy || props.rerouting} onMode={props.onMode} />
      <div className="relative h-[340px] overflow-hidden rounded-b-[17px] bg-water/30 min-[820px]:h-auto min-[820px]:flex-1">
        <MapView
          trip={trip}
          theme={props.theme}
          animKey={props.animKey}
          selectedId={selectedId}
          hoveredId={props.hoveredId}
          reducedMotion={props.reducedMotion}
          onSelect={props.onSelect}
        />
        <AnimatePresence>
          {selected && <InfoCard key={selected.id} stop={selected} index={index} onClose={() => props.onSelect(null)} />}
        </AnimatePresence>
        <AnimatePresence>
          {(notice || props.rerouting) && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              role="status"
              className="panel absolute top-3 left-1/2 z-10 flex -translate-x-1/2 items-center gap-2.5 px-3.5 py-2 text-[13px]"
            >
              {props.rerouting ? (
                <>
                  <span className="spin-ring" /> Rota yeniden hesaplanıyor…
                </>
              ) : (
                <>
                  {notice}
                  <button type="button" onClick={props.onDismissNotice} className="text-muted hover:text-text" aria-label="Kapat">
                    ✕
                  </button>
                </>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}
