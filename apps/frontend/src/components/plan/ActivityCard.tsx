"use client";
import { useState } from "react";
import type { Activity } from "@/lib/types";
import { Sparkles, ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";

type Q = { prompt?: string; question?: string; text?: string; options?: string[]; choices?: string[]; answer?: unknown; correct?: unknown; explanation?: string };

export function ActivityCard({ activity }: { activity: Activity }) {
  const payload = activity.payload ?? ({} as Activity["payload"]);
  const questions = Array.isArray(payload.questions) ? (payload.questions as Q[]) : [];
  const [open, setOpen] = useState(false);

  return (
    <div className="panel p-3">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2 text-left">
        <Sparkles className="h-4 w-4 text-accent" />
        <span className="text-sm font-medium">{payload.title || "Activity"}</span>
        <span className="chip-accent ml-auto">{payload.kind ?? "quiz"} · {questions.length}</span>
        <ChevronDown className={cn("h-4 w-4 text-fg-muted transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <ol className="mt-3 space-y-3">
          {questions.map((q, i) => <QuestionBlock key={i} q={q} n={i + 1} />)}
          {questions.length === 0 && <li className="text-xs text-fg-muted">No questions.</li>}
        </ol>
      )}
    </div>
  );
}

function QuestionBlock({ q, n }: { q: Q; n: number }) {
  const prompt = q.prompt ?? q.question ?? q.text ?? "";
  const options = q.options ?? q.choices ?? [];
  const correct = q.answer ?? q.correct;
  const [picked, setPicked] = useState<number | null>(null);
  return (
    <li className="rounded-lg border border-border dark:border-border-dark p-2">
      <p className="text-sm"><span className="text-fg-muted">Q{n}.</span> {prompt}</p>
      {options.length > 0 ? (
        <ul className="mt-2 space-y-1">
          {options.map((opt, i) => {
            const isPicked = picked === i;
            const isCorrect = picked !== null && matches(opt, i, correct);
            return (
              <li key={i}>
                <button
                  onClick={() => setPicked(i)}
                  className={cn(
                    "w-full rounded-md border px-2 py-1.5 text-left text-xs transition",
                    picked === null && "border-border dark:border-border-dark hover:bg-bg-subtle dark:hover:bg-bg-dark",
                    picked !== null && isCorrect && "border-accent bg-accent/10",
                    picked !== null && isPicked && !isCorrect && "border-err bg-err-soft dark:bg-err/10",
                  )}
                >
                  <span className="mr-2 font-mono text-fg-muted">{String.fromCharCode(65 + i)}.</span>{opt}
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="mt-2 text-xs text-fg-muted">Open-ended</p>
      )}
      {picked !== null && q.explanation && (
        <p className="mt-2 text-xs text-fg-muted"><strong>Explanation:</strong> {q.explanation}</p>
      )}
    </li>
  );
}

function matches(opt: string, i: number, correct: unknown): boolean {
  if (typeof correct === "number") return correct === i;
  if (typeof correct === "string") return correct === opt || correct === String.fromCharCode(65 + i);
  if (Array.isArray(correct)) return correct.includes(opt) || correct.includes(i);
  return false;
}
