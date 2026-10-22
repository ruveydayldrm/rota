"use client";

import maplibregl, { type GeoJSONSource, type Map as MLMap, type Marker } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { loadMapStyle, MAP_PALETTE, type ResolvedTheme } from "@/lib/mapStyle";
import type { Trip } from "@/lib/types";

interface Props {
  trip: Trip | null;
  theme: ResolvedTheme;
  animKey: number;
  selectedId: string | null;
  hoveredId: string | null;
  reducedMotion: boolean;
  onSelect: (id: string | null) => void;
}

const ROUTE_SOURCE = "rota-route";
const DRAW_MS = 2500;
const PIN_GAP_S = 0.3;
const TRANSPARENT = "rgba(0,0,0,0)";

function gradient(progress: number, color: string) {
  if (progress <= 0) return ["interpolate", ["linear"], ["line-progress"], 0, TRANSPARENT, 1, TRANSPARENT];
  if (progress >= 1) return ["interpolate", ["linear"], ["line-progress"], 0, color, 1, color];
  return ["step", ["line-progress"], color, progress, TRANSPARENT];
}

function lineData(trip: Trip | null): GeoJSON.Feature<GeoJSON.LineString> {
  return {
    type: "Feature",
    properties: {},
    geometry: { type: "LineString", coordinates: trip?.route.geometry ?? [] },
  };
}

function ensureRouteLayers(map: MLMap, theme: ResolvedTheme, trip: Trip | null, progress: number) {
  const p = MAP_PALETTE[theme];
  if (!map.getSource(ROUTE_SOURCE)) {
    map.addSource(ROUTE_SOURCE, { type: "geojson", lineMetrics: true, data: lineData(trip) });
  }
  if (!map.getLayer("rota-route-base")) {
    map.addLayer({
      id: "rota-route-base",
      type: "line",
      source: ROUTE_SOURCE,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": p.routeBase, "line-width": 3, "line-opacity": 0.55, "line-dasharray": [0, 2] },
    });
  }
  if (!map.getLayer("rota-route-line")) {
    map.addLayer({
      id: "rota-route-line",
      type: "line",
      source: ROUTE_SOURCE,
      layout: { "line-cap": "round", "line-join": "round" },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      paint: { "line-width": 4.5, "line-gradient": gradient(progress, p.accent) as any },
    });
  }
}

function boundsOf(trip: Trip): maplibregl.LngLatBounds | null {
  const coords = trip.route.geometry.length ? trip.route.geometry : trip.stops.map((s) => [s.lon, s.lat] as [number, number]);
  if (!coords.length) return null;
  const b = new maplibregl.LngLatBounds(coords[0], coords[0]);
  coords.forEach((c) => b.extend(c));
  trip.stops.forEach((s) => b.extend([s.lon, s.lat]));
  return b;
}

function makePin(index: number, name: string, delay: number, onClick: () => void): HTMLElement {
  const el = document.createElement("button");
  el.type = "button";
  el.className = "rota-pin";
  el.setAttribute("aria-label", `${index + 1}. durak: ${name}`);
  el.innerHTML = `
    <span class="rota-pin__inner" style="--delay:${delay}s">
      <span class="rota-pin__halo"></span>
      <span class="rota-pin__drop"><span class="rota-pin__num">${index + 1}</span></span>
      <span class="rota-pin__label"></span>
    </span>`;
  el.querySelector(".rota-pin__label")!.textContent = name;
  el.addEventListener("click", (e) => {
    e.stopPropagation();
    onClick();
  });
  return el;
}

type Box = { x1: number; x2: number; y1: number; y2: number };
const overlaps = (a: Box, b: Box) => !(a.x2 < b.x1 || a.x1 > b.x2 || a.y2 < b.y1 || a.y1 > b.y2);

/** Sık bölgelerde etiketler üst üste binmesin: çakışanı gizle, seçili/üzerine gelineni hep göster. */
function resolveLabelCollisions(map: MLMap, trip: Trip | null, markers: Map<string, Marker>) {
  const stops = trip?.stops ?? [];
  const points = stops.map((s) => map.project([s.lon, s.lat]));
  const placed: Box[] = points.map((p) => ({ x1: p.x - 16, x2: p.x + 16, y1: p.y - 38, y2: p.y - 4 }));
  const order = stops
    .map((s, i) => ({ s, i, el: markers.get(s.id)?.getElement() }))
    .sort((a, b) => Number(b.el?.matches(".is-selected, .is-hovered")) - Number(a.el?.matches(".is-selected, .is-hovered")));
  for (const { s, i, el } of order) {
    const label = el?.querySelector<HTMLElement>(".rota-pin__label");
    if (!el || !label) continue;
    const p = points[i];
    const box = { x1: p.x + 20, x2: p.x + 22 + (label.offsetWidth || s.name.length * 7), y1: p.y - 30, y2: p.y - 14 };
    const forced = el.matches(".is-selected, .is-hovered");
    const hide = !forced && placed.some((b, j) => j !== i && overlaps(box, b));
    el.classList.toggle("label-hidden", hide);
    if (!hide) placed.push(box);
  }
}

export default function MapView({ trip, theme, animKey, selectedId, hoveredId, reducedMotion, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const markersRef = useRef<Map<string, Marker>>(new Map());
  const progressRef = useRef(1);
  const frameRef = useRef<number | null>(null);
  const tripRef = useRef(trip);
  const themeRef = useRef(theme);
  const onSelectRef = useRef(onSelect);
  const [ready, setReady] = useState(false);
  const [bearing, setBearing] = useState(0);
  const [failed, setFailed] = useState(false);

  tripRef.current = trip;
  onSelectRef.current = onSelect;

  // Haritayı bir kez oluştur
  useEffect(() => {
    let cancelled = false;
    loadMapStyle(themeRef.current)
      .then((style) => {
        if (cancelled || !containerRef.current) return;
        const t = tripRef.current;
        const map = new maplibregl.Map({
          container: containerRef.current,
          style,
          center: t?.center ?? [28.977, 41.005],
          zoom: 13,
          attributionControl: { compact: true },
          dragRotate: true,
          fadeDuration: 0,
        });
        map.addControl(new maplibregl.ScaleControl({ maxWidth: 110, unit: "metric" }), "bottom-right");
        map.on("rotate", () => setBearing(map.getBearing()));
        map.on("moveend", () => resolveLabelCollisions(map, tripRef.current, markersRef.current));
        map.on("click", () => onSelectRef.current(null));
        // Karoları beklemeden: stil hazır olur olmaz rota katmanları eklenir (tema değişiminde de tekrar).
        map.on("style.load", () => {
          ensureRouteLayers(map, themeRef.current, tripRef.current, progressRef.current);
          setReady(true);
        });
        mapRef.current = map;
      })
      .catch(() => setFailed(true));
    return () => {
      cancelled = true;
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  // Tema değişince stili değiştir, rota katmanlarını geri ekle
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || themeRef.current === theme) return;
    themeRef.current = theme;
    let cancelled = false;
    loadMapStyle(theme).then((style) => {
      if (!cancelled) map.setStyle(style, { diff: false });
    });
    return () => {
      cancelled = true;
    };
  }, [theme, ready]);

  // Pinler: yeni rota geldiğinde 0.3 sn arayla düşerler
  const stopSignature = trip?.stops.map((s) => s.id).join("|") ?? "";
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    markersRef.current.forEach((m) => m.remove());
    markersRef.current.clear();
    const stops = tripRef.current?.stops ?? [];
    stops.forEach((stop, i) => {
      const el = makePin(i, stop.name, reducedMotion ? 0 : 0.15 + i * PIN_GAP_S, () => onSelectRef.current(stop.id));
      const marker = new maplibregl.Marker({ element: el, anchor: "bottom", offset: [0, -6] }).setLngLat([stop.lon, stop.lat]).addTo(map);
      markersRef.current.set(stop.id, marker);
    });
  }, [stopSignature, animKey, ready, reducedMotion]);

  // Seçili / üzerine gelinen pin
  useEffect(() => {
    markersRef.current.forEach((marker, id) => {
      const el = marker.getElement();
      el.classList.toggle("is-selected", id === selectedId);
      el.classList.toggle("is-hovered", id === hoveredId);
      el.setAttribute("aria-pressed", String(id === selectedId));
    });
    const map = mapRef.current;
    if (map && ready) requestAnimationFrame(() => resolveLabelCollisions(map, tripRef.current, markersRef.current));
  }, [selectedId, hoveredId, stopSignature, animKey, ready]);

  // Rota: soluk noktalı çizgi + ~2.5 sn'de baştan sona çizilen turuncu çizgi, ardından fitBounds
  const route = trip?.route;
  useEffect(() => {
    const map = mapRef.current;
    const current = tripRef.current;
    if (!map || !ready || !current) return;
    ensureRouteLayers(map, themeRef.current, current, 0);
    (map.getSource(ROUTE_SOURCE) as GeoJSONSource).setData(lineData(current));

    const bounds = boundsOf(current);
    if (bounds) {
      const narrow = map.getContainer().clientWidth < 560;
      map.fitBounds(bounds, {
        padding: narrow ? { top: 40, bottom: 40, left: 30, right: 90 } : { top: 70, bottom: 70, left: 70, right: 170 },
        duration: reducedMotion ? 0 : 1400,
        maxZoom: 16,
      });
    }

    const color = MAP_PALETTE[themeRef.current].accent;
    const setProgress = (p: number) => {
      progressRef.current = p;
      if (map.getLayer("rota-route-line")) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        map.setPaintProperty("rota-route-line", "line-gradient", gradient(p, color) as any);
      }
    };
    if (frameRef.current) cancelAnimationFrame(frameRef.current);
    if (reducedMotion) {
      setProgress(1);
      return;
    }
    setProgress(0);
    let start: number | null = null;
    const delay = 450;
    const tick = (now: number) => {
      start ??= now;
      const t = Math.min(Math.max((now - start - delay) / DRAW_MS, 0), 1);
      setProgress(1 - Math.pow(1 - t, 2.2));
      if (t < 1) frameRef.current = requestAnimationFrame(tick);
    };
    frameRef.current = requestAnimationFrame(tick);
  }, [route, animKey, ready, reducedMotion]);

  // Tema değişince turuncu tonunu güncelle
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const apply = () => {
      if (!map.getLayer("rota-route-line")) return;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      map.setPaintProperty("rota-route-line", "line-gradient", gradient(progressRef.current, MAP_PALETTE[theme].accent) as any);
      map.setPaintProperty("rota-route-base", "line-color", MAP_PALETTE[theme].routeBase);
    };
    if (map.isStyleLoaded()) apply();
    else map.once("idle", apply);
  }, [theme, ready]);

  // Seçili durağa yumuşak geçiş
  useEffect(() => {
    const map = mapRef.current;
    const stop = tripRef.current?.stops.find((s) => s.id === selectedId);
    if (!map || !stop) return;
    map.easeTo({ center: [stop.lon, stop.lat], duration: reducedMotion ? 0 : 700, offset: [0, -40] });
  }, [selectedId, reducedMotion]);

  return (
    <div className="absolute inset-0">
      {/* maplibregl-map kabı position:relative yapar; boyutu yüzdeyle veriyoruz */}
      <div ref={containerRef} className="h-full w-full" aria-label="Rota haritası" role="region" />
      {failed && (
        <div className="absolute inset-0 grid place-items-center bg-water/40 p-6 text-center text-[14px] text-muted">
          Harita karoları şu an yüklenemedi. Duraklar sohbet panelinde duruyor.
        </div>
      )}
      <button
        type="button"
        onClick={() => mapRef.current?.easeTo({ bearing: 0, pitch: 0, duration: reducedMotion ? 0 : 500 })}
        aria-label="Kuzeye döndür"
        title="Kuzeye döndür"
        className="absolute top-3 right-3 z-[1] grid size-11 place-items-center rounded-full border border-line bg-panel/85 text-muted backdrop-blur transition-colors hover:text-text"
      >
        <svg viewBox="0 0 40 40" className="size-9" style={{ transform: `rotate(${-bearing}deg)` }} aria-hidden="true">
          <circle cx="20" cy="20" r="15.5" fill="none" stroke="currentColor" strokeWidth="0.8" opacity="0.6" />
          {[0, 90, 180, 270].map((a) => (
            <line key={a} x1="20" y1="5.5" x2="20" y2="8.5" stroke="currentColor" strokeWidth="0.9" transform={`rotate(${a} 20 20)`} />
          ))}
          <path d="M20 9 L23 20 L20 18.6 L17 20 Z" fill="var(--accent)" />
          <path d="M20 31 L23 20 L20 21.4 L17 20 Z" fill="none" stroke="currentColor" strokeWidth="0.8" />
          <text x="20" y="4.6" textAnchor="middle" fontSize="4.6" fontFamily="var(--font-mono)" fill="currentColor">
            K
          </text>
        </svg>
      </button>
    </div>
  );
}
