import { API_URL, BUSY_MESSAGE } from "./config";
import type { Intent, Mode, RotaEvent, Trip } from "./types";

const EVENT_TYPES = new Set(["intent_parsed", "places_found", "stops_selected", "route_ready", "text_delta", "done", "error"]);

function parseBlock(block: string): RotaEvent | null {
  let type = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) type = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!EVENT_TYPES.has(type) || !data.length) return null;
  try {
    return { type, data: JSON.parse(data.join("\n")) } as RotaEvent;
  } catch {
    return null;
  }
}

/** POST + Server-Sent Events: backend'in her adımını geldiği anda verir. */
export async function* liveStream(
  message: string,
  tripId: string | null,
  context: Intent | null,
  signal?: AbortSignal,
): AsyncGenerator<RotaEvent> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ message, trip_id: tripId, context }),
      signal,
    });
  } catch {
    yield { type: "error", data: { message: "Sunucuya ulaşamadım. Birkaç saniye sonra tekrar dener misin?" } };
    return;
  }
  if (res.status === 429) {
    yield { type: "error", data: { message: BUSY_MESSAGE } };
    return;
  }
  if (!res.ok || !res.body) {
    yield { type: "error", data: { message: BUSY_MESSAGE } };
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const event = parseBlock(buffer.slice(0, idx));
      buffer = buffer.slice(idx + 2);
      if (event) yield event;
    }
  }
}

export async function recomputeRoute(tripId: string, mode: Mode): Promise<Trip> {
  const res = await fetch(`${API_URL}/api/route`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trip_id: tripId, mode }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? BUSY_MESSAGE);
  }
  return res.json();
}
