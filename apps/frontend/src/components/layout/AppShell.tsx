"use client";
import { useQueryState } from "nuqs";
import { useState } from "react";
import { Sidebar } from "./Sidebar";
import { CenterPlan } from "./CenterPlan";
import { AgentPane } from "./AgentPane";
import { useSyllabusStream } from "@/hooks/useSyllabusStream";
import { useSyllabusStore } from "@/hooks/useSyllabusStore";
import { cn } from "@/lib/cn";
import { Menu, X } from "lucide-react";

export function AppShell() {
  const [threadId, setThreadId] = useQueryState("thread");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const { stream, progress, resetProgress } = useSyllabusStream(threadId ?? undefined);
  const store = useSyllabusStore(threadId ?? undefined);

  return (
    <div className="flex h-full w-full flex-col md:flex-row">
      {/* Mobile top bar */}
      <header className="flex items-center justify-between gap-2 border-b border-border dark:border-border-dark
                         bg-panel/80 dark:bg-panel-dark/80 px-3 py-2 backdrop-blur md:hidden">
        <button onClick={() => setSidebarOpen((s) => !s)} className="btn-ghost p-2" aria-label="Toggle sidebar">
          {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
        <span className="text-sm font-semibold">{store.syllabus?.title ?? "MPFE"}</span>
        <span className="w-9" />
      </header>

      {/* Sidebar (drawer on mobile) */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 w-72 shrink-0 border-r border-border dark:border-border-dark",
          "bg-panel dark:bg-panel-dark transition-transform md:static md:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        )}
      >
        <Sidebar
          activeThreadId={threadId}
          onSelect={(id) => { setThreadId(id); setSidebarOpen(false); }}
          onNew={() => { setThreadId(null); resetProgress(); setSidebarOpen(false); }}
        />
      </aside>

      {sidebarOpen && (
        <button
          aria-label="Close sidebar"
          className="fixed inset-0 z-20 bg-black/30 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Center + right: stack on mobile, side-by-side on md+ */}
      <main className="flex min-h-0 flex-1 flex-col md:flex-row">
        <section className="min-h-0 flex-1 overflow-y-auto border-b border-border dark:border-border-dark md:border-b-0 md:border-r">
          <CenterPlan store={store} progress={progress} />
        </section>
        <section className="min-h-0 w-full shrink-0 md:w-[380px] lg:w-[420px]">
          <AgentPane
            stream={stream}
            progress={progress}
            threadId={threadId ?? undefined}
            onThreadCreated={setThreadId}
          />
        </section>
      </main>
    </div>
  );
}
