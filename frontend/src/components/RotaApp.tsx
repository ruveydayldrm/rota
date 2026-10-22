"use client";

import { MotionConfig } from "framer-motion";
import { IS_DEMO } from "@/lib/config";
import { useReducedMotion, useTheme } from "@/lib/theme";
import { useRota } from "@/lib/useRota";
import ChatPanel from "./chat/ChatPanel";
import MapPanel from "./map/MapPanel";
import TopBar from "./TopBar";

export default function RotaApp() {
  const { state, send, setMode, select, hover, dismissNotice } = useRota();
  const theme = useTheme();
  const reducedMotion = useReducedMotion();

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-dvh flex-col min-[820px]:h-dvh">
        <TopBar demo={IS_DEMO} theme={theme.pref} onTheme={theme.setPref} />
        <main className="flex flex-1 flex-col gap-3 px-3 pb-3 min-[820px]:grid min-[820px]:min-h-0 min-[820px]:grid-cols-[400px_minmax(0,1fr)] min-[820px]:grid-rows-[minmax(0,1fr)]">
          <MapPanel
            className="min-[820px]:order-2"
            trip={state.trip}
            theme={theme.resolved}
            animKey={state.animKey}
            busy={state.busy}
            rerouting={state.rerouting}
            notice={state.notice}
            selectedId={state.selectedId}
            hoveredId={state.hoveredId}
            reducedMotion={reducedMotion}
            onSelect={select}
            onMode={setMode}
            onDismissNotice={dismissNotice}
          />
          <ChatPanel
            className="flex-1 min-[820px]:order-1"
            messages={state.messages}
            trip={state.trip}
            busy={state.busy}
            selectedId={state.selectedId}
            onSend={send}
            onSelect={(id) => select(state.selectedId === id ? null : id)}
            onHover={hover}
          />
        </main>
        <footer className="sr-only">Harita verisi © OpenStreetMap katkıcıları</footer>
      </div>
    </MotionConfig>
  );
}
