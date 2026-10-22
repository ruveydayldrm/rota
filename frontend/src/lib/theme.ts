"use client";

import { useCallback, useEffect, useState } from "react";
import type { ResolvedTheme } from "./mapStyle";

export type ThemePref = "system" | "light" | "dark";
const KEY = "rota-theme";

function readPref(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

export function useTheme() {
  const [pref, setPrefState] = useState<ThemePref>("system");
  const [systemDark, setSystemDark] = useState(false);

  useEffect(() => {
    setPrefState(readPref());
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    setSystemDark(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const setPref = useCallback((next: ThemePref) => {
    setPrefState(next);
    const root = document.documentElement;
    if (next === "system") delete root.dataset.theme;
    else root.dataset.theme = next;
    try {
      if (next === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, next);
    } catch {
      /* gizli pencere vb. */
    }
  }, []);

  const resolved: ResolvedTheme = pref === "system" ? (systemDark ? "dark" : "light") : pref;
  return { pref, setPref, resolved };
}

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}
