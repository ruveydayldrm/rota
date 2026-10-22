"use client";

import { motion } from "framer-motion";
import type { BotMessage as Bot, Trip } from "@/lib/types";
import StopList from "./StopList";
import ToolCalls from "./ToolCalls";

export function UserBubble({ text }: { text: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="flex justify-end"
    >
      <p className="max-w-[85%] rounded-[16px] rounded-br-[5px] bg-bubble px-3.5 py-2 text-[14.5px] leading-snug text-bubble-text">
        {text}
      </p>
    </motion.div>
  );
}

export function TypingDots() {
  return (
    <div className="flex items-center gap-1 py-1" role="status" aria-label="Rota yazıyor">
      <span className="typing-dot" />
      <span className="typing-dot" style={{ animationDelay: "0.15s" }} />
      <span className="typing-dot" style={{ animationDelay: "0.3s" }} />
    </div>
  );
}

interface BotProps {
  message: Bot;
  trip: Trip | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
}

export function BotMessage({ message, trip, selectedId, onSelect, onHover }: BotProps) {
  const { steps, intent, intro, outro, stops, status, error } = message;
  const streaming = status === "streaming";
  const introDone = outro.length > 0 || status !== "streaming";
  const waitingForText = streaming && !intro;
  // Durak listesi yalnızca güncel rotaya aitse haritayla etkileşir.
  const interactive = Boolean(trip && stops && stops.every((s) => trip.stops.some((t) => t.id === s.id)));
  const shownStops = interactive && trip ? trip.stops.filter((t) => stops!.some((s) => s.id === t.id)) : stops;

  return (
    <article className="space-y-3" aria-label="Rota'nın yanıtı">
      <header className="flex items-center gap-2">
        <span className="grid size-[22px] place-items-center rounded-full bg-accent font-display text-[13px] leading-none font-extrabold text-white">
          r
        </span>
        <span className="font-display text-[14.5px] font-bold tracking-[-0.02em]">Rota</span>
      </header>

      {steps.length > 0 && <ToolCalls steps={steps} intent={intent} />}

      {waitingForText && !error && <TypingDots />}

      {intro && (
        <p className={`text-[15px] leading-relaxed ${streaming && !introDone ? "caret" : ""}`}>{intro}</p>
      )}

      {shownStops && shownStops.length > 0 && introDone && (
        <StopList stops={shownStops} selectedId={selectedId} interactive={interactive} onSelect={onSelect} onHover={onHover} />
      )}

      {outro && <p className={`text-[15px] leading-relaxed ${streaming ? "caret" : ""}`}>{outro}</p>}

      {error && (
        <p role="alert" className="rounded-xl border border-accent/40 bg-accent-soft px-3 py-2 text-[14px] leading-snug">
          {error}
        </p>
      )}
    </article>
  );
}
