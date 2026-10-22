"use client";

import { useEffect, useMemo, useRef } from "react";
import type { ChatMessage, Trip } from "@/lib/types";
import Composer from "./Composer";
import { BotMessage, UserBubble } from "./Messages";

interface Props {
  className?: string;
  messages: ChatMessage[];
  trip: Trip | null;
  busy: boolean;
  selectedId: string | null;
  onSend: (text: string) => void;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
}

const STARTERS = ["Kapadokya'da gün batımına kadar, araçla", "Mardin'de taş sokaklarda bir gün", "İstanbul'da tarih dolu bir gün"];

function suggestionsFor(trip: Trip | null): string[] {
  if (!trip) return STARTERS;
  const sight = trip.stops.find((s) => s.category !== "restoran" && s.category !== "kafe" && s !== trip.stops[0]);
  const other = STARTERS.find((s) => !s.toLocaleLowerCase("tr").includes(trip.city.toLocaleLowerCase("tr")));
  return [
    trip.route.mode === "yuruyus" ? "Araçla olsun" : "Yürüyerek olsun",
    "Öğle yemeğini değiştir",
    ...(sight ? [`${sight.name} olmasın`] : []),
    ...(other ? [other] : []),
  ];
}

export default function ChatPanel({ className = "", messages, trip, busy, selectedId, onSend, onSelect, onHover }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const last = messages[messages.length - 1];
  const lastLength = last?.role === "bot" ? last.intro.length + last.outro.length + last.steps.length : 0;
  const suggestions = useMemo(() => suggestionsFor(trip), [trip]);

  const initialCount = useRef(messages.length);
  useEffect(() => {
    // İlk açılıştaki örnek sohbet baştan okunsun; yalnızca yeni mesajlarda aşağı kay.
    if (messages.length === initialCount.current) return;
    const el = scrollRef.current;
    if (!el || el.scrollHeight <= el.clientHeight) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages.length, lastLength]);

  return (
    <section aria-label="Sohbet" className={`panel flex min-h-0 flex-col ${className}`}>
      <div ref={scrollRef} role="log" aria-label="Sohbet geçmişi" className="thin-scroll flex-1 space-y-6 overflow-y-auto px-4 pt-5 pb-6 min-[820px]:min-h-0">
        {messages.map((m) =>
          m.role === "user" ? (
            <UserBubble key={m.id} text={m.text} />
          ) : (
            <BotMessage key={m.id} message={m} trip={trip} selectedId={selectedId} onSelect={onSelect} onHover={onHover} />
          ),
        )}
      </div>
      <div className="sticky bottom-0 z-10 rounded-b-[18px] border-t border-line bg-panel/95 px-3 pt-2.5 pb-3 backdrop-blur">
        <Composer busy={busy} suggestions={suggestions} onSend={onSend} />
      </div>
    </section>
  );
}
