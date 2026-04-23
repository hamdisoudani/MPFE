"use client";
import type { AgentProgress, TimelineStep } from "@/hooks/useAgentProgress";
import type { AgentEvent } from "@/lib/types";
import { Search, BookOpen, Pencil, Sparkles, CircleCheck, AlertTriangle, Loader2, HelpCircle, PencilLine, Gavel } from "lucide-react";
import { cn } from "@/lib/cn";

export function AgentTimeline({ progress, streaming }: { progress: AgentProgress; streaming: boolean }) {
  const steps = progress.timeline;
  if (steps.length === 0 && !streaming) return null;

  return (
    <section className="panel p-3 md:p-4">
      <header className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-fg-muted">
        <span>Steps</span>
        <span className="ml-auto font-normal normal-case">{progress.eventCount} events</span>
      </header>
      <ol className="relative space-y-2 border-l border-border dark:border-border-dark pl-4">
        {steps.map((s, i) => (
          <TimelineRow key={s.id} step={s} active={streaming && i === steps.length - 1} />
        ))}
        {streaming && (
          <li className="relative flex items-center gap-2 text-xs text-fg-muted">
            <span className="absolute -left-[21px] flex h-3.5 w-3.5 items-center justify-center rounded-full bg-panel dark:bg-panel-dark">
              <Loader2 className="h-3 w-3 animate-spin text-accent" />
            </span>
            agent is working…
          </li>
        )}
      </ol>
    </section>
  );
}

function TimelineRow({ step, active }: { step: TimelineStep; active: boolean }) {
  const { icon: Icon, title, detail, tone } = describe(step.event);
  return (
    <li className="relative">
      <span className={cn(
        "absolute -left-[21px] flex h-3.5 w-3.5 items-center justify-center rounded-full",
        "bg-panel dark:bg-panel-dark ring-2",
        tone === "err" ? "ring-err" : tone === "ok" ? "ring-accent" : active ? "ring-accent animate-pulse" : "ring-border dark:ring-border-dark",
      )}>
        <Icon className={cn("h-2.5 w-2.5", tone === "err" ? "text-err" : "text-accent")} />
      </span>
      <div className="flex min-w-0 items-baseline gap-2">
        <span className="truncate text-sm text-fg dark:text-fg-dark">{title}</span>
        {detail && <span className="truncate text-xs text-fg-muted">· {detail}</span>}
      </div>
    </li>
  );
}

function describe(e: AgentEvent): { icon: any; title: string; detail?: string; tone?: "ok" | "err" | "neutral" } {
  switch (e.type) {
    case "phase_changed": return { icon: phaseIcon(e.phase), title: phaseLabel(e.phase), tone: e.phase === "done" ? "ok" : e.phase === "failed" ? "err" : "neutral" };
    case "search_progress": return { icon: Search, title: "Researching", detail: `${e.queries_done}/${e.queries_total} queries · ${e.findings} findings` };
    case "syllabus_created": return { icon: BookOpen, title: "Syllabus created", detail: e.title, tone: "ok" };
    case "chapter_started": return { icon: BookOpen, title: `Chapter ${e.position}`, detail: e.title };
    case "lesson_attempt": return { icon: e.status === "drafting" ? PencilLine : Gavel, title: e.status === "drafting" ? "Drafting lesson" : "Critiquing lesson", detail: `ch${e.chapter_pos}·L${e.position} · attempt ${e.attempt}` };
    case "critic_verdict": return { icon: Gavel, title: `Critic · ${e.score}/10`, detail: e.passes ? "passed" : `retry: ${e.weaknesses.slice(0, 2).join(", ")}`, tone: e.passes ? "ok" : "neutral" };
    case "lesson_committed": return { icon: CircleCheck, title: "Lesson committed", detail: `${e.attempts} attempt${e.attempts > 1 ? "s" : ""}${e.needs_review ? " · review" : ""}`, tone: "ok" };
    case "activities_generated": return { icon: Sparkles, title: "Activities generated", detail: `${e.count}` };
    case "error": return { icon: AlertTriangle, title: `Error · ${e.node}`, detail: e.message, tone: "err" };
    default: return { icon: HelpCircle, title: (e as any).type };
  }
}

function phaseIcon(p: string) {
  return p === "searching" ? Search : p === "outlining" ? BookOpen : p === "writing" ? Pencil : p === "activities" ? Sparkles : p === "done" ? CircleCheck : p === "failed" ? AlertTriangle : p === "awaiting_input" ? HelpCircle : Loader2;
}
function phaseLabel(p: string) {
  return p === "searching" ? "Researching the web"
    : p === "outlining" ? "Drafting the outline"
    : p === "writing" ? "Writing lessons"
    : p === "activities" ? "Generating activities"
    : p === "awaiting_input" ? "Waiting for answers"
    : p === "done" ? "Completed" : p === "failed" ? "Failed" : p;
}
