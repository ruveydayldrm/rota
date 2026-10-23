"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { Intent, ToolStep } from "@/lib/types";

function StatusMark({ status }: { status: ToolStep["status"] }) {
  if (status === "running") return <span className="spin-ring shrink-0" aria-label="sürüyor" />;
  if (status === "error") return <span className="size-[9px] shrink-0 rounded-full bg-accent" aria-label="hata" />;
  return <span className="size-[9px] shrink-0 rounded-full bg-success" aria-label="tamamlandı" />;
}

function IntentBox({ intent }: { intent: Intent }) {
  const entries = Object.entries(intent).filter(([, v]) => v !== null && v !== undefined && !(Array.isArray(v) && !v.length));
  return (
    <motion.pre
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      transition={{ duration: 0.3 }}
      className="thin-scroll mt-1.5 mb-0.5 overflow-x-auto rounded-lg border border-line bg-surface px-3 py-2 text-[11.5px] leading-[1.55] text-muted"
      aria-label="Ayrıştırılan niyet"
    >
      {"{\n"}
      {entries.map(([k, v], i) => (
        <span key={k}>
          {"  "}
          <span>&quot;{k}&quot;</span>: <span className="text-accent">{JSON.stringify(v)}</span>
          {i < entries.length - 1 ? ",\n" : "\n"}
        </span>
      ))}
      {"}"}
    </motion.pre>
  );
}

export default function ToolCalls({ steps, intent }: { steps: ToolStep[]; intent?: Intent | null }) {
  return (
    <ol className="relative ml-[3px] space-y-1.5 border-l border-line pl-4 font-mono text-[11.5px] text-muted" aria-label="Araç çağrıları">
      <AnimatePresence initial={false}>
        {steps.map((step) => (
          <motion.li
            key={step.key}
            layout
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.25 }}
          >
            <div className="flex items-center gap-2.5">
              <StatusMark status={step.status} />
              <span className={step.status === "done" ? "text-text/85" : undefined}>
                {step.label} {step.source && <span className="text-muted/70">· {step.source}</span>}
              </span>
            </div>
            {step.key === "intent" && step.status === "done" && intent && <IntentBox intent={intent} />}
          </motion.li>
        ))}
      </AnimatePresence>
    </ol>
  );
}
