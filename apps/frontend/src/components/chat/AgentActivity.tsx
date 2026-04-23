"use client";
import type { AgentProgress } from "@/hooks/useAgentProgress";
import type { Phase } from "@/lib/types";
import { Loader2, Search, BookOpen, Pencil, CircleCheck, Sparkles, HelpCircle } from "lucide-react";

const PHASE_COPY: Record<Phase, { label: string; Icon: any }> = {
  searching:      { label: "Researching the web", Icon: Search },
  awaiting_input: { label: "Waiting for your answers", Icon: HelpCircle },
  outlining:      { label: "Drafting the outline", Icon: BookOpen },
  writing:        { label: "Writing lessons", Icon: Pencil },
  activities:     { label: "Generating activities", Icon: Sparkles },
  done:           { label: "Done", Icon: CircleCheck },
  failed:         { label: "Failed", Icon: CircleCheck },
};

export function AgentActivity({ progress, streaming }: { progress: AgentProgress; streaming: boolean }) {
  const phase = progress.phase;
  if (!phase && !streaming) return null;
  const meta = phase ? PHASE_COPY[phase] : { label: "Working…", Icon: Loader2 };
  const spin = streaming && phase !== "done" && phase !== "failed" && phase !== "awaiting_input";

  return (
    <div className="rounded-xl border border-border dark:border-border-dark bg-panel dark:bg-panel-dark p-3 text-xs text-fg-muted">
      <div className="flex items-center gap-2">
        {spin ? <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" /> : <meta.Icon className="h-3.5 w-3.5 text-accent" />}
        <span className="font-medium text-fg dark:text-fg-dark">{meta.label}</span>
      </div>

      {progress.searchProgress && phase === "searching" && (
        <div className="mt-2">
          <div className="flex justify-between">
            <span>{progress.searchProgress.done}/{progress.searchProgress.total} queries</span>
            <span>{progress.searchProgress.findings} findings</span>
          </div>
          <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-border/60 dark:bg-border-dark/60">
            <div className="h-full bg-accent transition-all"
                 style={{ width: `${progress.searchProgress.total ? Math.min(100, Math.round(progress.searchProgress.done / progress.searchProgress.total * 100)) : 0}%` }} />
          </div>
        </div>
      )}

      {progress.activeChapter && (phase === "writing" || phase === "outlining") && (
        <div className="mt-2">
          <span className="text-fg dark:text-fg-dark">Chapter {progress.activeChapter.position}:</span>{" "}
          <span className="truncate">{progress.activeChapter.title}</span>
        </div>
      )}

      {progress.activeLesson && (
        <div className="mt-1">
          L{progress.activeLesson.position} · attempt {progress.activeLesson.attempt} · {progress.activeLesson.status}
          {typeof progress.activeLesson.lastScore === "number" && (
            <span className="ml-1">· critic {progress.activeLesson.lastScore}/10 {progress.activeLesson.lastPassed ? "✓" : "✗"}</span>
          )}
        </div>
      )}

      {progress.lastCommitted && phase !== "searching" && (
        <div className="mt-1">Last committed · lesson {progress.lastCommitted.lessonId.slice(0, 6)} · {progress.lastCommitted.attempts} attempts</div>
      )}
    </div>
  );
}
