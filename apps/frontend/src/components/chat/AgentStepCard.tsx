"use client";
import { memo } from "react";
import type { TimelineStep } from "@/hooks/useAgentProgress";
import type { AgentEvent } from "@/lib/types";
import { Search, BookOpen, Sparkles, CircleCheck, AlertTriangle, Loader2, HelpCircle, PencilLine, Gavel } from "lucide-react";
import { cn } from "@/lib/cn";

export const AgentStepCard = memo(function AgentStepCard({ step, active }: { step: TimelineStep; active: boolean }) {
  const { icon: Icon, title, detail, tone } = describe(step.event);
  return (
    <div className={cn(
      "flex items-start gap-2 rounded-xl border px-3 py-2 text-sm animate-fade-in",
      tone === "err" ? "border-err/40 bg-err-soft dark:bg-err/10"
        : tone === "ok" ? "border-accent/30 bg-accent/5"
        : "border-border dark:border-border-dark bg-panel dark:bg-panel-dark",
    )}>
      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", tone === "err" ? "text-err" : "text-accent", active && "animate-pulse")} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-xs font-medium">{title}</div>
        {detail && <div className="truncate text-xs text-fg-muted">{detail}</div>}
      </div>
    </div>
  );
});

function describe(e: AgentEvent): { icon: any; title: string; detail?: string; tone?: "ok" | "err" | "neutral" } {
  switch (e.type) {
    case "phase_changed": return { icon: phaseIcon(e.phase), title: phaseLabel(e.phase), tone: e.phase === "done" ? "ok" : e.phase === "failed" ? "err" : "neutral" };
    case "search_progress": return { icon: Search, title: "Researching", detail: `${e.queries_done}/${e.queries_total} queries · ${e.findings} findings` };
    case "syllabus_created": return { icon: BookOpen, title: "Syllabus created", detail: e.title, tone: "ok" };
    case "chapter_started": return { icon: BookOpen, title: `Chapter ${e.position}`, detail: e.title };
    case "lesson_attempt": return { icon: e.status === "drafting" ? PencilLine : Gavel, title: e.status === "drafting" ? "Drafting lesson" : "Critiquing lesson", detail: `ch${e.chapter_pos} · L${e.position} · attempt ${e.attempt}` };
    case "critic_verdict": return { icon: Gavel, title: `Critic · ${e.score}/10`, detail: e.passes ? "passed" : `retry: ${(e.weaknesses||[]).slice(0,2).join(", ")}`, tone: e.passes ? "ok" : "neutral" };
    case "lesson_committed": return { icon: CircleCheck, title: "Lesson committed", detail: `${e.attempts} attempt${e.attempts>1?"s":""}${e.needs_review?" · review":""}`, tone: "ok" };
    case "activities_generated": return { icon: Sparkles, title: "Activities generated", detail: `${e.count}` };
    case "error": return { icon: AlertTriangle, title: `Error · ${e.node}`, detail: e.message, tone: "err" };
    default: return { icon: HelpCircle, title: (e as any).type };
  }
}
function phaseIcon(p: string) { return p === "searching" ? Search : p === "outlining" ? BookOpen : p === "writing" ? PencilLine : p === "activities" ? Sparkles : p === "done" ? CircleCheck : p === "failed" ? AlertTriangle : p === "awaiting_input" ? HelpCircle : Loader2; }
function phaseLabel(p: string) { return p === "searching" ? "Researching the web" : p === "outlining" ? "Drafting the outline" : p === "writing" ? "Writing lessons" : p === "activities" ? "Generating activities" : p === "awaiting_input" ? "Waiting for answers" : p === "done" ? "Completed" : p === "failed" ? "Failed" : p; }
