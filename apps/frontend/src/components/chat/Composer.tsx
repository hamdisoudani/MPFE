"use client";
import { Send } from "lucide-react";
import { cn } from "@/lib/cn";

export function Composer({
  draft, setDraft, disabled, onSubmit, variant = "inline", placeholder,
}: {
  draft: string; setDraft: (v: string) => void;
  disabled: boolean; onSubmit: () => void;
  variant?: "inline" | "hero";
  placeholder?: string;
}) {
  const isHero = variant === "hero";
  const ph = placeholder ??
    (isHero
      ? "What do you want to teach? e.g. \"A 6-week intro to Python for high-schoolers, focus on problem-solving.\""
      : "Send a follow-up, or answer the agent…");

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onSubmit(); }}
      className={cn(
        isHero
          ? "rounded-2xl border border-border dark:border-border-dark bg-panel dark:bg-panel-dark p-3 shadow-sm"
          : "border-t border-border dark:border-border-dark p-3"
      )}
    >
      <textarea
        className={cn(
          "w-full resize-none bg-transparent outline-none placeholder:text-fg-muted",
          isHero ? "min-h-[110px] text-base leading-relaxed px-2 py-1" : "min-h-[64px] text-sm leading-relaxed"
        )}
        placeholder={ph}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        disabled={disabled}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSubmit(); }
        }}
      />
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-[10px] text-fg-muted">Enter to send · Shift+Enter for newline</span>
        <button type="submit" className="btn-primary" disabled={disabled || !draft.trim()}>
          <Send className="h-3.5 w-3.5" /> {isHero ? "Start" : "Send"}
        </button>
      </div>
    </form>
  );
}
