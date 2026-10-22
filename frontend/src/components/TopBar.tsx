"use client";

import type { ThemePref } from "@/lib/theme";

function LogoMark() {
  return (
    <svg width="26" height="18" viewBox="0 0 26 18" aria-hidden="true" className="shrink-0">
      <path
        d="M4 14 C 9 14, 9 4, 13 4 S 17 14, 22 4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeDasharray="0.1 3.2"
        className="text-muted"
      />
      <circle cx="4" cy="14" r="2.6" fill="var(--panel)" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="22" cy="4" r="2.6" fill="var(--accent)" />
    </svg>
  );
}

const THEMES: { value: ThemePref; label: string; icon: React.ReactNode }[] = [
  {
    value: "system",
    label: "Sistem teması",
    icon: (
      <svg viewBox="0 0 16 16" className="size-3.5" aria-hidden="true">
        <rect x="2" y="3" width="12" height="8.5" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.3" />
        <path d="M6 13.5h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    value: "light",
    label: "Açık tema",
    icon: (
      <svg viewBox="0 0 16 16" className="size-3.5" aria-hidden="true">
        <circle cx="8" cy="8" r="3" fill="none" stroke="currentColor" strokeWidth="1.3" />
        <path
          d="M8 1.5v1.6M8 12.9v1.6M1.5 8h1.6M12.9 8h1.6M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M3.4 12.6l1.1-1.1M11.5 4.5l1.1-1.1"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
  {
    value: "dark",
    label: "Koyu tema",
    icon: (
      <svg viewBox="0 0 16 16" className="size-3.5" aria-hidden="true">
        <path d="M13 9.6A5.5 5.5 0 0 1 6.4 3a5.5 5.5 0 1 0 6.6 6.6Z" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
      </svg>
    ),
  },
];

export default function TopBar({ demo, theme, onTheme }: { demo: boolean; theme: ThemePref; onTheme: (t: ThemePref) => void }) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 px-4 min-[820px]:px-5">
      <div className="flex min-w-0 items-center gap-3">
        <a href="/" className="flex items-center gap-2 rounded-md text-text" aria-label="Rota ana sayfa">
          <LogoMark />
          <span className="font-display text-[22px] leading-none font-extrabold tracking-[-0.06em]">rota</span>
        </a>
        <span className="hidden h-4 w-px bg-line sm:block" aria-hidden="true" />
        <p className="hidden truncate text-[13.5px] text-muted sm:block">Ne sevdiğini söyle, günü haritada kuralım.</p>
      </div>

      <div className="flex shrink-0 items-center gap-2.5">
        {demo && (
          <span
            className="rounded-full border border-dashed border-muted/60 px-2.5 py-1 font-mono text-[11px] text-muted"
            title="Bu sürüm backend'e bağlanmadan, gerçek verilerden hazırlanmış örneklerle çalışır."
          >
            Demo · örnek veriler
          </span>
        )}
        <div role="radiogroup" aria-label="Tema" className="flex rounded-full border border-line bg-panel p-0.5">
          {THEMES.map((t) => (
            <button
              key={t.value}
              type="button"
              role="radio"
              aria-checked={theme === t.value}
              aria-label={t.label}
              title={t.label}
              onClick={() => onTheme(t.value)}
              className={`grid size-7 place-items-center rounded-full transition-colors ${
                theme === t.value ? "bg-surface text-text" : "text-muted hover:text-text"
              }`}
            >
              {t.icon}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}
