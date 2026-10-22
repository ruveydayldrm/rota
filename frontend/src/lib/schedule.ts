// backend/app/pipeline/schedule.py ile aynı kurallar: demo ve canlı mod aynı saatleri üretir.
import type { Mode, Route, Stop } from "./types";

export const VISIT_MIN: Record<string, number> = {
  muze: 75,
  cami: 35,
  kilise: 35,
  dini: 35,
  tarih: 45,
  park: 40,
  doga: 60,
  manzara: 25,
  restoran: 60,
  kafe: 30,
  carsi: 50,
  sanat: 45,
  turizm: 45,
};
const DEFAULT_VISIT = 45;
export const SPEED_KMH: Record<Mode, number> = { yuruyus: 4.5, arac: 30 };
export const DETOUR = 1.3;

export function haversineKm(a: [number, number], b: [number, number]): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const [lat1, lon1] = a.map(toRad);
  const [lat2, lon2] = b.map(toRad);
  const h = Math.sin((lat2 - lat1) / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin((lon2 - lon1) / 2) ** 2;
  return 2 * 6371.0088 * Math.asin(Math.sqrt(h));
}

const round5 = (m: number) => Math.floor(m / 5 + 0.5) * 5;

export function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

export function fmtHHMM(minutes: number): string {
  const m = ((minutes % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

export function scheduleTimes(stops: Pick<Stop, "category">[], legsMin: number[], start = "09:00"): string[] {
  let t = toMinutes(start);
  return stops.map((s, i) => {
    const out = fmtHHMM(round5(t));
    t += VISIT_MIN[s.category] ?? DEFAULT_VISIT;
    if (i < legsMin.length) t += legsMin[i];
    return out;
  });
}

/** Düz çizgi + ortalama hız: rota servisi yoksa kullanılan tahmin. */
export function straightLeg(a: Stop, b: Stop, mode: Mode) {
  const km = haversineKm([a.lat, a.lon], [b.lat, b.lon]) * DETOUR;
  return {
    geometry: [
      [a.lon, a.lat],
      [b.lon, b.lat],
    ] as [number, number][],
    distance_km: km,
    duration_min: (km / SPEED_KMH[mode]) * 60,
  };
}

export function totalDayMinutes(trip: { stops: Stop[]; route: Route }): number {
  const { stops } = trip;
  if (!stops.length) return 0;
  const last = stops[stops.length - 1];
  return toMinutes(last.time) + (VISIT_MIN[last.category] ?? DEFAULT_VISIT) - toMinutes(stops[0].time);
}
