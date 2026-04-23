"use client";
import { Send } from "lucide-react";

export function Composer({
  draft, setDraft, title, setTitle, showTitle, disabled, onSubmit,
}: {
  draft: string; setDraft: (v: string) => void;
  title: string; setTitle: (v: string) => void;
  showTitle: boolean; disabled: boolean; onSubmit: () => void;
}) {
  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onSubmit(); }}
      className="border-t border-border dark:border-border-dark p-3 space-y-2"
    >
      {showTitle && (
        <input className="input" placeholder="Optional title — e.g. Python for beginners"
               value={title} onChange={(e) => setTitle(e.target.value)} disabled={disabled} />
      )}
      <textarea
        className="input min-h-[72px] resize-y"
        placeholder="Describe what you want to teach — audience, topics, focus, duration…"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        disabled={disabled}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); onSubmit(); }
        }}
      />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] text-fg-muted">Enter for newline · ⌘/Ctrl+Enter to send</span>
        <button type="submit" className="btn-primary" disabled={disabled || !draft.trim()}>
          <Send className="h-3.5 w-3.5" /> Send
        </button>
      </div>
    </form>
  );
}
