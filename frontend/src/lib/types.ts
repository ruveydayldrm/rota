export type Mode = "yuruyus" | "arac";

export interface Intent {
  sehir: string;
  ilce?: string | null;
  ilgi: string[];
  sure: "yarim_gun" | "1_gun" | "2_gun";
  mod: Mode;
  baslangic_saati?: string | null;
  ozel_istekler: string[];
}

export interface WikiInfo {
  extract?: string | null;
  image?: string | null;
  url?: string | null;
}

export interface Stop {
  id: string;
  name: string;
  lat: number;
  lon: number;
  category: string;
  time: string;
  tip: string;
  wiki?: WikiInfo | null;
}

export interface Route {
  geometry: [number, number][];
  distance_km: number;
  duration_min: number;
  mode: Mode;
  source: "osrm" | "ors" | "straight";
  legs_min: number[];
}

export interface Trip {
  id: string;
  city: string;
  center: [number, number];
  intent: Intent;
  stops: Stop[];
  route: Route;
  intro: string;
  outro: string;
  candidates_count: number;
}

export type RotaEvent =
  | { type: "intent_parsed"; data: { intent: Intent | null } }
  | { type: "places_found"; data: { count: number } }
  | { type: "stops_selected"; data: { stops: Stop[] } }
  | { type: "route_ready"; data: { route: Route; stops: Stop[]; city: string; center: [number, number] } }
  | { type: "text_delta"; data: { text: string; part: "intro" | "outro" } }
  | { type: "done"; data: { trip: Trip | null } }
  | { type: "error"; data: { message: string } };

export type StepKey = "intent" | "places" | "stops" | "route";

export interface ToolStep {
  key: StepKey;
  label: string;
  source: string;
  status: "running" | "done" | "error";
}

export interface UserMessage {
  role: "user";
  id: string;
  text: string;
}

export interface BotMessage {
  role: "bot";
  id: string;
  steps: ToolStep[];
  intent?: Intent | null;
  intro: string;
  outro: string;
  stops?: Stop[];
  status: "streaming" | "done" | "error";
  error?: string;
}

export type ChatMessage = UserMessage | BotMessage;
