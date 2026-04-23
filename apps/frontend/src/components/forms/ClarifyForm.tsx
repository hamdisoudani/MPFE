"use client";
import { useMemo, useState } from "react";
import type { ClarificationInterrupt, ClarificationQuestion } from "@/lib/types";

export function ClarifyForm({
  interrupt, onSubmit,
}: { interrupt: ClarificationInterrupt; onSubmit: (answers: Record<string, unknown>) => Promise<void> | void }) {
  const initial = useMemo(() => Object.fromEntries(
    interrupt.questions.map((q) => [q.key, q.default ?? defaultFor(q.kind)])
  ), [interrupt]);
  const [values, setValues] = useState<Record<string, unknown>>(initial);
  const [submitting, setSubmitting] = useState(false);

  return (
    <div className="panel p-4">
      <div className="mb-3">
        <span className="chip-warn"><span className="dot text-warn" /> waiting on your answers</span>
      </div>
      <p className="mb-3 text-sm text-fg-muted">{interrupt.findings_summary}</p>

      <form
        className="space-y-3"
        onSubmit={async (e) => {
          e.preventDefault();
          setSubmitting(true);
          try { await onSubmit(values); } finally { setSubmitting(false); }
        }}
      >
        {interrupt.questions.map((q) => (
          <Field key={q.key} q={q}
                 value={values[q.key]}
                 onChange={(v) => setValues((s) => ({ ...s, [q.key]: v }))} />
        ))}
        <button type="submit" className="btn-primary w-full sm:w-auto" disabled={submitting}>
          {submitting ? "Submitting…" : "Continue"}
        </button>
      </form>
    </div>
  );
}

function defaultFor(kind: ClarificationQuestion["kind"]) {
  switch (kind) { case "number": return 0; case "boolean": return false;
    case "multi_choice": return []; default: return ""; }
}

function Field({ q, value, onChange }: { q: ClarificationQuestion; value: any; onChange: (v: any) => void }) {
  return (
    <label className="block">
      <div className="mb-1 text-sm font-medium">{q.prompt}</div>
      {q.rationale && <div className="mb-1.5 text-xs text-fg-muted">{q.rationale}</div>}
      {q.kind === "text" && (
        <input className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value)} />
      )}
      {q.kind === "number" && (
        <input type="number" className="input" value={value ?? 0}
               onChange={(e) => onChange(Number(e.target.value))} />
      )}
      {q.kind === "boolean" && (
        <label className="inline-flex items-center gap-2 text-sm">
          <input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />
          <span>Yes</span>
        </label>
      )}
      {q.kind === "single_choice" && (
        <select className="input" value={String(value ?? "")} onChange={(e) => onChange(e.target.value)}>
          <option value="" disabled>Choose…</option>
          {(q.options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      )}
      {q.kind === "multi_choice" && (
        <div className="flex flex-wrap gap-2">
          {(q.options ?? []).map((o) => {
            const arr: string[] = Array.isArray(value) ? value : [];
            const on = arr.includes(o);
            return (
              <button key={o} type="button"
                      onClick={() => onChange(on ? arr.filter((x) => x !== o) : [...arr, o])}
                      className={"chip cursor-pointer " + (on ? "chip-accent" : "")}>
                {o}
              </button>
            );
          })}
        </div>
      )}
    </label>
  );
}
