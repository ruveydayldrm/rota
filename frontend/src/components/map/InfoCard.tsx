"use client";

import { motion } from "framer-motion";
import { useEffect } from "react";
import { formatCoordsCompact, googleMapsUrl } from "@/lib/format";
import type { Stop } from "@/lib/types";

interface Props {
  stop: Stop;
  index: number;
  onClose: () => void;
}

export default function InfoCard({ stop, index, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const wiki = stop.wiki;
  return (
    <motion.aside
      key={stop.id}
      initial={{ opacity: 0, y: 14, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.98 }}
      transition={{ duration: 0.25, ease: [0.2, 0.8, 0.2, 1] }}
      aria-label={`${stop.name} bilgileri`}
      className="panel absolute bottom-3 left-3 z-10 w-[min(340px,calc(100%-24px))] p-4"
    >
      <div className="flex items-start gap-3">
        <span className="tnum grid size-7 shrink-0 place-items-center rounded-full bg-accent font-mono text-[12px] font-bold text-white">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-[19px] leading-tight font-bold tracking-[-0.03em]">{stop.name}</h2>
          {stop.tip && <p className="mt-1 text-[13.5px] leading-snug text-muted">{stop.tip}</p>}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Kartı kapat"
          className="-mt-1 -mr-1 grid size-7 shrink-0 place-items-center rounded-full text-muted hover:bg-surface hover:text-text"
        >
          <svg viewBox="0 0 16 16" className="size-3.5" aria-hidden="true">
            <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {(wiki?.extract || wiki?.image) && (
        <div className="mt-3 flex gap-3 border-t border-line pt-3">
          {wiki.extract && (
            <p className="line-clamp-5 flex-1 text-[12.5px] leading-relaxed">
              {wiki.extract}
              {wiki.url && (
                <>
                  {" "}
                  <a href={wiki.url} target="_blank" rel="noreferrer" className="text-muted underline decoration-line underline-offset-2 hover:text-accent">
                    Wikipedia
                  </a>
                </>
              )}
            </p>
          )}
          {wiki.image && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={wiki.image}
              alt={stop.name}
              loading="lazy"
              referrerPolicy="no-referrer"
              className="size-[76px] shrink-0 rounded-lg border border-line object-cover"
            />
          )}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
        <span className="tnum font-mono text-[11px] text-muted">
          {stop.time} · {formatCoordsCompact(stop.lat, stop.lon)}
        </span>
        <a
          href={googleMapsUrl(stop.lat, stop.lon)}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 rounded-md text-[12.5px] font-semibold text-accent hover:underline"
        >
          Google Haritalar&apos;da aç
          <svg viewBox="0 0 16 16" className="size-3" aria-hidden="true">
            <path d="M6 3h7v7M13 3 4 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </a>
      </div>
    </motion.aside>
  );
}
