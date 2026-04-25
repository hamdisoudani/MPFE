"use client";
/**
 * ChapterQuiz — renders an `Activity` with payload.kind="quiz" and grades
 * the learner's answers locally against `correct_index` per question.
 *
 * The MPFE agent writes this payload directly to `activities.payload` JSONB
 * (see apps/agent/agent/tools/db_tools.py::exec_commit_activity). The
 * frontend does the scoring client-side — no backend submission.
 */
import { useMemo, useState } from "react";
import type { Activity, QuizQuestion } from "@/store/syllabusStore";
import { CheckCircle2, ClipboardCheck, RotateCcw, Send, XCircle } from "lucide-react";

interface Props {
  activity: Activity;
  onSubmitted?: (r: { score: number; total: number }) => void;
}

function qKey(i: number): string {
  return `q${i}`;
}

function isCorrect(q: QuizQuestion, picked: number | null): boolean {
  return picked !== null && picked === q.correct_index;
}

export default function ChapterQuiz({ activity, onSubmitted }: Props) {
  const questions = activity.payload?.questions ?? [];
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [submitted, setSubmitted] = useState(false);

  const result = useMemo(() => {
    if (!submitted) return null;
    let score = 0;
    for (let i = 0; i < questions.length; i++) {
      if (isCorrect(questions[i], answers[qKey(i)] ?? null)) score += 1;
    }
    return { score, total: questions.length };
  }, [submitted, answers, questions]);

  function pick(i: number, opt: number) {
    if (submitted) return;
    setAnswers((prev) => ({ ...prev, [qKey(i)]: opt }));
  }

  function handleSubmit() {
    setSubmitted(true);
    if (onSubmitted && questions.length) {
      let score = 0;
      for (let i = 0; i < questions.length; i++) {
        if (isCorrect(questions[i], answers[qKey(i)] ?? null)) score += 1;
      }
      onSubmitted({ score, total: questions.length });
    }
  }

  function handleReset() {
    setAnswers({});
    setSubmitted(false);
  }

  if (!questions.length) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="rounded-lg border border-dashed border-[var(--border)] p-6 text-sm text-[var(--muted-foreground)]">
          This quiz has no questions yet. It is still being generated…
        </div>
      </div>
    );
  }

  return (
    <div className="h-full w-full overflow-y-auto bg-background">
      <div className="mx-auto w-full max-w-3xl px-6 py-8">
        <header className="mb-6 flex items-start justify-between border-b border-[var(--border)] pb-4">
          <div>
            <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-[var(--muted-foreground)]">
              <ClipboardCheck className="h-3.5 w-3.5" />
              <span>Activity · Quiz</span>
            </div>
            <h1 className="mt-1 text-2xl font-semibold text-foreground">
              {activity.title ?? "Untitled activity"}
            </h1>
            <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
              {questions.length} question{questions.length === 1 ? "" : "s"}
            </p>
          </div>
          {submitted && result ? (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-right">
              <div className="text-[11px] uppercase text-[var(--muted-foreground)]">Score</div>
              <div className="text-xl font-semibold">
                {result.score}/{result.total}
              </div>
            </div>
          ) : null}
        </header>

        {activity.payload?.instructions ? (
          <p className="mb-6 rounded-lg bg-[var(--accent)] p-3 text-sm text-[var(--foreground)]">
            {activity.payload.instructions}
          </p>
        ) : null}

        <ol className="flex flex-col gap-4">
          {questions.map((q, idx) => {
            const picked = answers[qKey(idx)] ?? null;
            const correct = submitted ? isCorrect(q, picked) : null;
            return (
              <li
                key={idx}
                className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
              >
                <div className="flex items-start gap-2">
                  <span className="text-sm font-medium text-[var(--muted-foreground)]">
                    {idx + 1}.
                  </span>
                  <p className="flex-1 text-sm font-medium text-foreground">{q.prompt}</p>
                  {submitted ? (
                    correct ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/20 px-2 py-0.5 text-[11px] font-semibold text-emerald-300">
                        <CheckCircle2 className="h-3 w-3" /> Correct
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/20 px-2 py-0.5 text-[11px] font-semibold text-rose-300">
                        <XCircle className="h-3 w-3" /> Incorrect
                      </span>
                    )
                  ) : q.difficulty ? (
                    <span className="rounded bg-[var(--muted)] px-1.5 py-0.5 text-[10px] uppercase text-[var(--muted-foreground)]">
                      {q.difficulty}
                    </span>
                  ) : null}
                </div>

                <ul className="mt-3 flex flex-col gap-1.5">
                  {q.options.map((opt, optIdx) => {
                    const selected = picked === optIdx;
                    const isAnswer = optIdx === q.correct_index;
                    const feedbackClass = submitted
                      ? isAnswer
                        ? "border-emerald-500/60 bg-emerald-500/10"
                        : selected
                          ? "border-rose-500/60 bg-rose-500/10"
                          : "border-transparent"
                      : selected
                        ? "border-[var(--primary)] bg-[var(--primary)]/10"
                        : "border-[var(--border)] hover:bg-[var(--accent)]";
                    return (
                      <li key={optIdx}>
                        <button
                          type="button"
                          onClick={() => pick(idx, optIdx)}
                          disabled={submitted}
                          className={`w-full rounded-md border px-3 py-2 text-left text-sm transition-colors ${feedbackClass}`}
                        >
                          <span className="mr-2 font-mono text-xs text-[var(--muted-foreground)]">
                            {String.fromCharCode(65 + optIdx)}.
                          </span>
                          {opt}
                        </button>
                      </li>
                    );
                  })}
                </ul>

                {submitted && q.explanation ? (
                  <p className="mt-3 rounded-md border border-[var(--border)] bg-[var(--muted)]/50 p-2 text-xs leading-relaxed text-[var(--muted-foreground)]">
                    <span className="font-semibold text-foreground">Explanation: </span>
                    {q.explanation}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ol>

        <div className="mt-6 flex items-center gap-2">
          {!submitted ? (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={Object.keys(answers).length !== questions.length}
              className="inline-flex items-center gap-2 rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-[var(--primary-foreground)] disabled:opacity-50"
            >
              <Send className="h-4 w-4" /> Submit
            </button>
          ) : (
            <button
              type="button"
              onClick={handleReset}
              className="inline-flex items-center gap-2 rounded-md border border-[var(--border)] px-4 py-2 text-sm font-semibold text-foreground hover:bg-[var(--accent)]"
            >
              <RotateCcw className="h-4 w-4" /> Retry
            </button>
          )}
          <span className="text-xs text-[var(--muted-foreground)]">
            {Object.keys(answers).length}/{questions.length} answered
          </span>
        </div>
      </div>
    </div>
  );
}
