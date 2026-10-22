// Demo modu: backend'e hiç gitmeden, gerçek OSM/OSRM/Wikipedia verisinden üretilmiş hazır JSON'larla çalışır.
// Veriler backend/scripts/build_demo.py ile yeniden üretilebilir.
import istanbul from "./data/istanbul.json";
import kapadokya from "./data/kapadokya.json";
import mardin from "./data/mardin.json";
import { trLower } from "../format";
import { scheduleTimes, straightLeg } from "../schedule";
import type { Intent, Mode, RotaEvent, Stop, Trip } from "../types";

interface DemoLeg {
  g: [number, number][];
  km: number;
  min: number;
}

export interface DemoCity {
  key: string;
  city: string;
  center: [number, number];
  keywords: string[];
  intent: Intent;
  start: string;
  candidates_count: number;
  intro: string;
  outro: string;
  stops: Stop[];
  lunch_alt: Stop;
  legs: Record<Mode, Record<string, DemoLeg>>;
}

export const DEMO_CITIES = [istanbul, kapadokya, mardin] as unknown as DemoCity[];

let tripCounter = 0;

export function cityOfTrip(trip: Trip | null): DemoCity | null {
  if (!trip?.id.startsWith("demo-")) return null;
  const key = trip.id.split("-")[1];
  return DEMO_CITIES.find((c) => c.key === key) ?? null;
}

export function buildTrip(city: DemoCity, ids: string[], mode: Mode, base?: Partial<Trip>): Trip {
  const pool = new Map([...city.stops, city.lunch_alt].map((s) => [s.id, s]));
  const stops = ids.map((id) => pool.get(id)).filter((s): s is Stop => Boolean(s));

  const geometry: [number, number][] = [];
  const legsMin: number[] = [];
  let km = 0;
  let allReal = true;
  stops.slice(0, -1).forEach((a, i) => {
    const b = stops[i + 1];
    const leg = city.legs[mode][`${a.id}>${b.id}`];
    const g = leg ? leg.g : straightLeg(a, b, mode).geometry;
    const legKm = leg ? leg.km : straightLeg(a, b, mode).distance_km;
    const legMin = leg ? leg.min : straightLeg(a, b, mode).duration_min;
    if (!leg) allReal = false;
    geometry.push(...(geometry.length ? g.slice(1) : g));
    legsMin.push(legMin);
    km += legKm;
  });

  const times = scheduleTimes(stops, legsMin, city.start);
  tripCounter += 1;
  return {
    id: `demo-${city.key}-${tripCounter}`,
    city: city.city,
    center: city.center,
    intent: { ...city.intent, mod: mode },
    stops: stops.map((s, i) => ({ ...s, time: times[i] })),
    route: {
      geometry,
      distance_km: Math.round(km * 100) / 100,
      duration_min: Math.round(legsMin.reduce((a, b) => a + b, 0) * 10) / 10,
      mode,
      source: allReal ? "osrm" : "straight",
      legs_min: legsMin,
    },
    intro: base?.intro ?? city.intro,
    outro: base?.outro ?? city.outro,
    candidates_count: city.candidates_count,
  };
}

export function defaultDemoTrip(key = "istanbul", mode?: Mode): Trip {
  const city = DEMO_CITIES.find((c) => c.key === key) ?? DEMO_CITIES[0];
  return buildTrip(city, city.stops.map((s) => s.id), mode ?? city.intent.mod);
}

export function demoRemode(trip: Trip, mode: Mode): Trip | null {
  const city = cityOfTrip(trip);
  if (!city) return null;
  return buildTrip(city, trip.stops.map((s) => s.id), mode, trip);
}

// --- Mesaj yorumlama ---------------------------------------------------------

function matchCity(text: string): DemoCity | null {
  return DEMO_CITIES.find((c) => c.keywords.some((k) => text.includes(k))) ?? null;
}

function detectMode(text: string): Mode | null {
  if (/(araç|araba|otomobil|sürüş|kiralık)/.test(text)) return "arac";
  if (/(yürü|yaya|yürüyüş)/.test(text)) return "yuruyus";
  return null;
}

const GENERIC = new Set([
  "camii", "sarayı", "müzesi", "vadisi", "kalesi", "tarihi", "medresesi", "açık", "hava", "restaurant",
  "kilisesi", "çarşısı", "konağı", "sarnıcı", "kulesi",
]);

function findStopIn(text: string, stops: Stop[]): Stop | null {
  for (const stop of stops) {
    const stems = trLower(stop.name)
      .split(/[\s']+/)
      .filter((w) => w.length >= 4 && !GENERIC.has(w))
      .map((w) => w.slice(0, 5));
    if (stems.some((s) => text.includes(s))) return stop;
  }
  return null;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function* streamText(text: string, part: "intro" | "outro"): AsyncGenerator<RotaEvent> {
  for (const chunk of text.match(/\S+\s*/g) ?? []) {
    yield { type: "text_delta", data: { text: chunk, part } };
    await sleep(24);
  }
}

async function* playTrip(trip: Trip, intro: string, outro: string, firstRun: boolean): AsyncGenerator<RotaEvent> {
  yield { type: "intent_parsed", data: { intent: trip.intent } };
  await sleep(firstRun ? 950 : 500);
  yield { type: "places_found", data: { count: trip.candidates_count } };
  await sleep(firstRun ? 1150 : 600);
  yield { type: "stops_selected", data: { stops: trip.stops } };
  await sleep(firstRun ? 850 : 550);
  yield { type: "route_ready", data: { route: trip.route, stops: trip.stops, city: trip.city, center: trip.center } };
  await sleep(250);
  yield* streamText(intro, "intro");
  yield* streamText(outro, "outro");
  yield { type: "done", data: { trip: { ...trip, intro, outro } } };
}

async function* reply(text: string): AsyncGenerator<RotaEvent> {
  await sleep(600);
  yield { type: "intent_parsed", data: { intent: null } };
  yield* streamText(text, "intro");
  yield { type: "done", data: { trip: null } };
}

const DEMO_HELP =
  "Demo modunda İstanbul, Kapadokya ve Mardin için gerçek verilerle hazırlanmış rotalar var. " +
  "Örneğin “Kapadokya'da gün batımına kadar, araçla” yazabilirsin.";

const EDIT_HELP =
  "Demo modunda şu değişiklikleri deneyebilirsin: bir durağı çıkarmak (“Ayasofya olmasın”), " +
  "öğle yemeğini değiştirmek ya da “araçla olsun” demek.";

export async function* demoStream(message: string, current: Trip | null): AsyncGenerator<RotaEvent> {
  const text = trLower(message);
  const named = matchCity(text);
  const mode = detectMode(text);
  const currentCity = cityOfTrip(current);

  // Yeni şehir ya da açıkça yeni plan
  if (named && (named.key !== currentCity?.key || !current)) {
    const trip = buildTrip(named, named.stops.map((s) => s.id), mode ?? named.intent.mod);
    yield* playTrip(trip, named.intro, named.outro, true);
    return;
  }

  if (!current || !currentCity) {
    yield* reply(DEMO_HELP);
    return;
  }

  const ids = current.stops.map((s) => s.id);

  if (/(çıkar|kaldır|olmasın|istemiyorum|atla|sil)/.test(text)) {
    const target = findStopIn(text, current.stops);
    if (!target) {
      yield* reply("Hangi durağı çıkarmamı istediğini anlayamadım. Durağın adını yazar mısın?");
      return;
    }
    if (ids.length <= 3) {
      yield* reply("Rotada zaten az durak kaldı; bunu çıkarırsam gün çok kısalır.");
      return;
    }
    const trip = buildTrip(currentCity, ids.filter((id) => id !== target.id), mode ?? current.route.mode);
    yield* playTrip(
      trip,
      `Tamam, ${target.name} rotadan çıktı. Kalan durakları aynı sırayla bağladım.`,
      "Yerine başka bir şey eklememi istersen söyle.",
      false,
    );
    return;
  }

  if (/(yemek|öğle|restoran|lokanta)/.test(text)) {
    const lunchIdx = current.stops.findIndex((s) => s.category === "restoran");
    if (lunchIdx < 0) {
      yield* reply("Bu rotada değiştirilecek bir yemek durağı yok.");
      return;
    }
    const original = currentCity.stops.find((s) => s.category === "restoran")!;
    const next = ids[lunchIdx] === original.id ? currentCity.lunch_alt : original;
    const newIds = [...ids];
    newIds[lunchIdx] = next.id;
    const trip = buildTrip(currentCity, newIds, mode ?? current.route.mode);
    yield* playTrip(trip, `Öğle yemeğini ${next.name} olarak değiştirdim.`, next.tip, false);
    return;
  }

  if (mode && mode !== current.route.mode) {
    const trip = buildTrip(currentCity, ids, mode);
    const how = mode === "arac" ? "araçla" : "yürüyerek";
    yield* playTrip(trip, `Tamam, aynı durakları ${how} gezilecek şekilde yeniden hesapladım.`, "Başka bir değişiklik istersen yazman yeterli.", false);
    return;
  }

  yield* reply(EDIT_HELP);
}
