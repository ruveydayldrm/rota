import type { StyleSpecification, LayerSpecification } from "maplibre-gl";

export type ResolvedTheme = "light" | "dark";

const BASE_STYLES: Record<ResolvedTheme, string> = {
  light: "https://tiles.openfreemap.org/styles/positron",
  dark: "https://tiles.openfreemap.org/styles/dark",
};

export const MAP_PALETTE = {
  light: {
    background: "#eef3f4",
    water: "#cadde4",
    park: "#dfe9e3",
    landuse: "#e6ecee",
    building: "#dde5e8",
    road: "#ffffff",
    roadCasing: "#d5dfe2",
    boundary: "#b9c6cb",
    label: "#5b6d75",
    halo: "#eef3f4",
    accent: "#d97a0f",
    routeBase: "#5b6d75",
  },
  dark: {
    background: "#111b20",
    water: "#14303a",
    park: "#15252a",
    landuse: "#131e23",
    building: "#18252b",
    road: "#22323a",
    roadCasing: "#1a282f",
    boundary: "#2c3e46",
    label: "#8fa2a9",
    halo: "#111b20",
    accent: "#f0a13b",
    routeBase: "#8fa2a9",
  },
} as const;

const HIDDEN_SOURCE_LAYERS = new Set(["poi", "aerodrome_label", "housenumber", "mountain_peak", "aeroway"]);

type AnyLayer = LayerSpecification & { "source-layer"?: string; paint?: Record<string, unknown>; layout?: Record<string, unknown> };

/** OpenFreeMap stilini Rota paletine uyarlar: sade, düşük kontrastlı, gereksiz POI'ler kapalı. */
function transform(style: StyleSpecification, theme: ResolvedTheme): StyleSpecification {
  const p = MAP_PALETTE[theme];
  const layers = (style.layers as AnyLayer[]).map((layer) => {
    const l: AnyLayer = { ...layer, paint: { ...(layer.paint ?? {}) }, layout: { ...(layer.layout ?? {}) } };
    const sl = l["source-layer"] ?? "";
    const paint = l.paint!;
    const layout = l.layout!;

    if (l.type === "background") {
      paint["background-color"] = p.background;
    } else if (l.type === "fill") {
      if (sl === "water") paint["fill-color"] = p.water;
      else if (sl === "park" || (sl === "landcover" && /wood|grass|park/.test(l.id))) {
        paint["fill-color"] = p.park;
        paint["fill-opacity"] = 0.8;
      } else if (sl === "building") {
        paint["fill-color"] = p.building;
        paint["fill-opacity"] = 0.55;
        delete paint["fill-outline-color"];
      } else if (sl === "landuse" || sl === "landcover") {
        paint["fill-color"] = p.landuse;
        paint["fill-opacity"] = 0.5;
      }
    } else if (l.type === "fill-extrusion") {
      layout.visibility = "none";
    } else if (l.type === "line") {
      if (sl === "waterway") paint["line-color"] = p.water;
      else if (sl === "transportation") {
        paint["line-color"] = /casing|outline/.test(l.id) ? p.roadCasing : p.road;
        if (/rail|transit/.test(l.id)) paint["line-opacity"] = 0.35;
      } else if (sl === "boundary") paint["line-color"] = p.boundary;
    } else if (l.type === "symbol") {
      if (HIDDEN_SOURCE_LAYERS.has(sl)) {
        layout.visibility = "none";
      } else {
        paint["text-color"] = p.label;
        paint["text-halo-color"] = p.halo;
        paint["text-halo-width"] = 1.3;
        if (sl === "transportation_name") paint["text-opacity"] = 0.8;
      }
    }
    return l as LayerSpecification;
  });
  return { ...style, layers };
}

const cache = new Map<ResolvedTheme, Promise<StyleSpecification>>();

export function loadMapStyle(theme: ResolvedTheme): Promise<StyleSpecification> {
  let pending = cache.get(theme);
  if (!pending) {
    pending = fetch(BASE_STYLES[theme])
      .then((r) => {
        if (!r.ok) throw new Error(`style ${r.status}`);
        return r.json() as Promise<StyleSpecification>;
      })
      .then((s) => transform(s, theme))
      .catch((err) => {
        cache.delete(theme);
        throw err;
      });
    cache.set(theme, pending);
  }
  return pending;
}
