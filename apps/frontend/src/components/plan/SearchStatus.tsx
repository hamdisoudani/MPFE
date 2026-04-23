"use client";
import type { AgentProgress } from "@/hooks/useAgentProgress";

export function SearchStatus({ progress }: { progress: AgentProgress }) {
  if (!progress.searchProgress) return null;
  const { done, total, findings } = progress.searchProgress;
  const pct = total ? Math.min(100, Math.round((done / total) * 100)) : 0;
  return (
    <div className="mt-4 rounded-xl border border-border dark:border-border-dark bg-panel dark:bg-panel-dark p-3">
      <div className="flex items-center justify-between text-xs text-fg-muted">
        <span>Research · {done}/{total} queries · {findings} findings</span>
        <span>{pct}%</span>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-border/60 dark:bg-border-dark/60">
        <div className="h-full bg-accent transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
