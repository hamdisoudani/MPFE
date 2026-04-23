"use client";
import { useThreadsSWR } from "@/hooks/useThreadsSWR";
import { Plus, CircleDot, CircleCheck, CircleAlert, PauseCircle } from "lucide-react";
import { cn } from "@/lib/cn";
import { readThreadStatus, threadTitle, type ThreadStatus } from "@/lib/threadStatus";

const STATUS_META: Record<ThreadStatus, { Icon: any; cls: string; label: string }> = {
  busy:        { Icon: CircleDot,   cls: "text-accent animate-pulse-dot", label: "running" },
  interrupted: { Icon: PauseCircle, cls: "text-warn",                     label: "waiting" },
  error:       { Icon: CircleAlert, cls: "text-err",                      label: "error" },
  idle:        { Icon: CircleCheck, cls: "text-fg-muted",                 label: "idle" },
};

export function Sidebar({
  activeThreadId, onSelect, onNew,
}: { activeThreadId: string | null | undefined; onSelect: (id: string) => void; onNew: () => void }) {
  const { threads, isLoading } = useThreadsSWR();

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-3 py-3">
        <span className="text-sm font-semibold">MPFE</span>
        <button className="btn-primary px-2.5 py-1.5 text-xs" onClick={onNew}>
          <Plus className="h-3.5 w-3.5" /> New
        </button>
      </div>
      <div className="scrollbar-thin flex-1 overflow-y-auto px-2 pb-3">
        {isLoading && <p className="px-2 py-1 text-xs text-fg-muted">Loading…</p>}
        {!isLoading && threads.length === 0 && (
          <p className="px-2 py-1 text-xs text-fg-muted">No threads yet. Start one on the right →</p>
        )}
        <ul className="space-y-1">
          {threads.map((t: any) => (
            <ThreadRow key={t.thread_id} thread={t} active={t.thread_id === activeThreadId} onSelect={onSelect} />
          ))}
        </ul>
      </div>
    </div>
  );
}

function ThreadRow({ thread, active, onSelect }: { thread: any; active: boolean; onSelect: (id: string) => void }) {
  const status = readThreadStatus(thread);
  const meta = STATUS_META[status];
  const title = threadTitle(thread);
  return (
    <li>
      <button
        onClick={() => onSelect(thread.thread_id)}
        className={cn(
          "group flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-left text-sm transition",
          active ? "bg-accent-soft text-fg dark:bg-accent/15" : "hover:bg-bg dark:hover:bg-bg-dark"
        )}
        title={`${meta.label} · ${thread.thread_id}`}
      >
        <meta.Icon className={cn("h-3.5 w-3.5 shrink-0", meta.cls)} />
        <span className="truncate flex-1">{title}</span>
        <span className={cn("hidden group-hover:inline text-[10px]", meta.cls)}>{meta.label}</span>
      </button>
    </li>
  );
}
