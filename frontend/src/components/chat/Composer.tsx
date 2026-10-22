"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  busy: boolean;
  suggestions: string[];
  onSend: (text: string) => void;
}

export default function Composer({ busy, suggestions, onSend }: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 132)}px`;
  }, [value]);

  const submit = (text: string) => {
    if (busy || !text.trim()) return;
    onSend(text);
    setValue("");
  };

  return (
    <div className="space-y-2.5">
      <div className="no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1 py-0.5" aria-label="Öneriler">
        {suggestions.map((s) => (
          <button
            key={s}
            type="button"
            disabled={busy}
            onClick={() => submit(s)}
            className="shrink-0 rounded-full border border-line px-3 py-1.5 text-[12.5px] whitespace-nowrap text-muted transition-colors enabled:hover:border-accent/60 enabled:hover:bg-accent-soft enabled:hover:text-accent disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(value);
        }}
        className="flex items-end gap-2 rounded-[14px] border border-line bg-surface p-1.5 pl-3.5 transition-colors focus-within:border-accent/60"
      >
        <label htmlFor="rota-input" className="sr-only">
          Mesajın
        </label>
        <textarea
          id="rota-input"
          ref={ref}
          rows={1}
          value={value}
          maxLength={500}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit(value);
            }
          }}
          placeholder="Örn. “Kapadokya'da gün batımına kadar, araçla”"
          className="max-h-[132px] flex-1 resize-none bg-transparent py-1.5 text-[14.5px] leading-snug outline-none placeholder:text-muted/70 focus-visible:outline-none"
        />
        <button
          type="submit"
          disabled={busy || !value.trim()}
          aria-label="Gönder"
          className="grid size-9 shrink-0 place-items-center rounded-[10px] bg-accent text-white transition-opacity disabled:opacity-35"
        >
          <svg viewBox="0 0 16 16" className="size-4" aria-hidden="true">
            <path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </form>
    </div>
  );
}
