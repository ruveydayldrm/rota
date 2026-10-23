"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { liveStream, recomputeRoute } from "./api";
import { BUSY_MESSAGE, IS_DEMO } from "./config";
import { cityOfTrip, defaultDemoTrip, demoRemode, demoStream } from "./demo/engine";
import { uid } from "./format";
import type { BotMessage, ChatMessage, Mode, RotaEvent, StepKey, ToolStep, Trip } from "./types";

export interface RotaState {
  messages: ChatMessage[];
  trip: Trip | null;
  busy: boolean;
  rerouting: boolean;
  selectedId: string | null;
  hoveredId: string | null;
  animKey: number;
  notice: string | null;
}

type Action =
  | { type: "start"; text: string; userId: string; botId: string }
  | { type: "event"; botId: string; event: RotaEvent }
  | { type: "finish"; botId: string }
  | { type: "select"; id: string | null }
  | { type: "hover"; id: string | null }
  | { type: "trip"; trip: Trip }
  | { type: "rerouting"; value: boolean }
  | { type: "notice"; message: string | null };

const MODE_LABEL: Record<Mode, string> = { yuruyus: "Yürüyüş", arac: "Araç" };
const SOURCE_LABEL = { osrm: "OSRM", ors: "OpenRouteService", straight: "tahmini" } as const;

function finishStep(steps: ToolStep[], key: StepKey, label: string, source: string): ToolStep[] {
  return steps.map((s) => (s.key === key ? { ...s, label, source, status: "done" } : s));
}

function addStep(steps: ToolStep[], key: StepKey, label: string, source: string): ToolStep[] {
  return [...steps, { key, label, source, status: "running" }];
}

function initialState(): RotaState {
  const trip = defaultDemoTrip("istanbul");
  const bot: BotMessage = {
    role: "bot",
    id: "intro-bot",
    steps: [
      { key: "intent", label: "İstek ayrıştırıldı", source: "LLM", status: "done" },
      { key: "places", label: `${trip.candidates_count} gerçek mekan bulundu`, source: "Overpass", status: "done" },
      { key: "stops", label: `${trip.stops.length} durak seçildi, sıralandı`, source: "LLM", status: "done" },
      { key: "route", label: "Yürüyüş rotası hesaplandı", source: "OSRM", status: "done" },
    ],
    intent: trip.intent,
    intro: trip.intro,
    outro: trip.outro,
    stops: trip.stops,
    status: "done",
  };
  return {
    messages: [{ role: "user", id: "intro-user", text: "İstanbul'da tarih dolu bir gün" }, bot],
    trip,
    busy: false,
    rerouting: false,
    selectedId: null,
    hoveredId: null,
    animKey: 1,
    notice: null,
  };
}

function applyEvent(state: RotaState, bot: BotMessage, event: RotaEvent): [RotaState, BotMessage] {
  switch (event.type) {
    case "intent_parsed": {
      const { intent, source } = event.data;
      let steps = finishStep(bot.steps, "intent", "İstek ayrıştırıldı", source ?? "LLM");
      if (intent) steps = addStep(steps, "places", "Gerçek mekanlar aranıyor", "OpenStreetMap");
      return [state, { ...bot, steps, intent }];
    }
    case "places_found": {
      const { count, source } = event.data;
      let steps = finishStep(bot.steps, "places", `${count} gerçek mekan bulundu`, source ?? "Overpass");
      steps = addStep(steps, "stops", "Duraklar seçiliyor", "");
      return [state, { ...bot, steps }];
    }
    case "stops_selected": {
      const mode = bot.intent?.mod ?? "yuruyus";
      const { source } = event.data;
      let steps = finishStep(bot.steps, "stops", `${event.data.stops.length} durak seçildi, sıralandı`, source ?? "LLM");
      steps = addStep(steps, "route", `${MODE_LABEL[mode]} rotası hesaplanıyor`, "OSRM");
      return [state, { ...bot, steps, stops: event.data.stops }];
    }
    case "route_ready": {
      const { route, stops, city, center } = event.data;
      const steps = finishStep(bot.steps, "route", `${MODE_LABEL[route.mode]} rotası hesaplandı`, SOURCE_LABEL[route.source]);
      const intent = bot.intent ?? state.trip?.intent;
      const trip: Trip | null = intent
        ? { id: "pending", city, center, intent: { ...intent, mod: route.mode }, stops, route, intro: "", outro: "", candidates_count: 0 }
        : state.trip;
      return [
        { ...state, trip, animKey: state.animKey + 1, selectedId: null },
        { ...bot, steps, stops },
      ];
    }
    case "text_delta": {
      const { part, text } = event.data;
      return [state, { ...bot, [part]: bot[part] + text }];
    }
    case "done": {
      const { trip } = event.data;
      if (!trip) return [state, { ...bot, status: "done" }];
      return [{ ...state, trip }, { ...bot, status: "done", stops: trip.stops }];
    }
    case "error": {
      const steps = bot.steps.map((s) => (s.status === "running" ? { ...s, status: "error" as const } : s));
      return [state, { ...bot, steps, status: "error", error: event.data.message }];
    }
  }
}

function reducer(state: RotaState, action: Action): RotaState {
  switch (action.type) {
    case "start": {
      const bot: BotMessage = {
        role: "bot",
        id: action.botId,
        steps: [{ key: "intent", label: "İstek ayrıştırılıyor", source: "", status: "running" }],
        intro: "",
        outro: "",
        status: "streaming",
      };
      return {
        ...state,
        busy: true,
        notice: null,
        messages: [...state.messages, { role: "user", id: action.userId, text: action.text }, bot],
      };
    }
    case "event": {
      const idx = state.messages.findIndex((m) => m.id === action.botId);
      const bot = state.messages[idx];
      if (idx < 0 || bot.role !== "bot") return state;
      const [next, updated] = applyEvent(state, bot, action.event);
      const messages = [...next.messages];
      messages[idx] = updated;
      return { ...next, messages };
    }
    case "finish": {
      const messages = state.messages.map((m) =>
        m.id === action.botId && m.role === "bot" && m.status === "streaming" ? { ...m, status: "done" as const } : m,
      );
      return { ...state, busy: false, messages };
    }
    case "select":
      return { ...state, selectedId: action.id };
    case "hover":
      return { ...state, hoveredId: action.id };
    case "trip":
      return { ...state, trip: action.trip, rerouting: false };
    case "rerouting":
      return { ...state, rerouting: action.value };
    case "notice":
      return { ...state, notice: action.message, rerouting: false };
  }
}

export function useRota() {
  const [state, dispatch] = useReducer(reducer, undefined, initialState);
  const stateRef = useRef(state);
  stateRef.current = state;
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const send = useCallback(async (raw: string) => {
    const message = raw.trim();
    if (!message || stateRef.current.busy) return;
    const botId = uid("bot");
    dispatch({ type: "start", text: message, userId: uid("user"), botId });

    const current = stateRef.current.trip;
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    const isDemoTrip = Boolean(cityOfTrip(current));
    const source = IS_DEMO
      ? demoStream(message, current)
      : liveStream(message, current && !isDemoTrip ? current.id : null, current?.intent ?? null, ctrl.signal);

    try {
      for await (const event of source) dispatch({ type: "event", botId, event });
    } catch {
      dispatch({ type: "event", botId, event: { type: "error", data: { message: BUSY_MESSAGE } } });
    } finally {
      dispatch({ type: "finish", botId });
    }
  }, []);

  const setMode = useCallback(async (mode: Mode) => {
    const trip = stateRef.current.trip;
    if (!trip || trip.route.mode === mode || stateRef.current.busy) return;
    const local = demoRemode(trip, mode);
    if (local) {
      dispatch({ type: "trip", trip: local });
      return;
    }
    dispatch({ type: "rerouting", value: true });
    try {
      dispatch({ type: "trip", trip: await recomputeRoute(trip.id, mode) });
    } catch (err) {
      dispatch({ type: "notice", message: err instanceof Error ? err.message : BUSY_MESSAGE });
    }
  }, []);

  const select = useCallback((id: string | null) => dispatch({ type: "select", id }), []);
  const hover = useCallback((id: string | null) => dispatch({ type: "hover", id }), []);
  const dismissNotice = useCallback(() => dispatch({ type: "notice", message: null }), []);

  return { state, send, setMode, select, hover, dismissNotice };
}
