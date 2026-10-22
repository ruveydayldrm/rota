export const INTEREST_LABELS: Record<string, string> = {
  tarih: "tarih",
  muze: "müze",
  dini: "dini yapılar",
  mimari: "mimari",
  park: "park",
  doga: "doğa",
  manzara: "manzara",
  yemek: "yemek",
  kahve: "kahve",
  sanat: "sanat",
  alisveris: "alışveriş",
};

export function formatCoords(lat: number, lon: number, digits = 3): string {
  const ns = lat >= 0 ? "K" : "G";
  const ew = lon >= 0 ? "D" : "B";
  return `${Math.abs(lat).toFixed(digits)}° ${ns} · ${Math.abs(lon).toFixed(digits)}° ${ew}`;
}

export function formatCoordsCompact(lat: number, lon: number): string {
  return `${Math.abs(lat).toFixed(4)}° ${lat >= 0 ? "K" : "G"}, ${Math.abs(lon).toFixed(4)}° ${lon >= 0 ? "D" : "B"}`;
}

export function interestsLabel(ilgi: string[]): string {
  return ilgi.map((i) => INTEREST_LABELS[i] ?? i).join(", ");
}

export function googleMapsUrl(lat: number, lon: number): string {
  return `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`;
}

export function trLower(text: string): string {
  return text.replace(/İ/g, "i").replace(/I/g, "ı").toLowerCase();
}

let counter = 0;
export function uid(prefix = "m"): string {
  counter += 1;
  return `${prefix}-${Date.now().toString(36)}-${counter}`;
}
