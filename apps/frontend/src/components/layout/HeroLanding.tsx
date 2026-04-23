"use client";
import { Composer } from "../chat/Composer";
import { useDraftStorage } from "@/hooks/useDraftStorage";
import { Sparkles } from "lucide-react";

const EXAMPLES = [
  "A 6-week intro to Python for high-schoolers, focus on problem-solving and small projects.",
  "Teach React hooks to junior developers — 8 short lessons, heavy on examples.",
  "Intermediate Spanish for travelers — 10 lessons, conversation-first, no heavy grammar.",
  "Data structures refresher for a SWE interview — arrays, trees, graphs, 2-week plan.",
];

export function HeroLanding({
  onSubmit, disabled,
}: { onSubmit: (requirements: string) => void; disabled: boolean }) {
  const { draft, setDraft, clearDraft } = useDraftStorage(undefined);

  const submit = () => {
    const t = draft.trim();
    if (!t) return;
    clearDraft();
    onSubmit(t);
  };

  return (
    <div className="mx-auto flex h-full min-h-[70vh] max-w-2xl flex-col items-center justify-center px-4 py-10">
      <div className="mb-5 inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-accent text-accent-fg dark:bg-fg-dark dark:text-bg-dark">
        <Sparkles className="h-5 w-5" />
      </div>
      <h1 className="text-center text-2xl font-semibold md:text-3xl">What should we teach?</h1>
      <p className="mt-2 text-center text-sm text-fg-muted">
        Describe the audience, topics and format. We&apos;ll research, outline and write the syllabus live.
      </p>

      <div className="mt-6 w-full">
        <Composer
          draft={draft}
          setDraft={setDraft}
          disabled={disabled}
          onSubmit={submit}
          variant="hero"
        />
      </div>

      <div className="mt-5 w-full">
        <p className="mb-2 text-xs text-fg-muted">Try one of these:</p>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => setDraft(ex)}
              className="chip hover:bg-accent-soft dark:hover:bg-fg-dark/10 cursor-pointer text-left"
            >
              {ex.length > 70 ? ex.slice(0, 70) + "…" : ex}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
