"use client";
import { useQueryState } from "nuqs";
import { useCallback, useEffect, useState } from "react";
import { Sidebar } from "./Sidebar";
import { CenterPlan } from "./CenterPlan";
import { AgentPane } from "./AgentPane";
import { HeroLanding } from "./HeroLanding";
import { useSyllabusStream } from "@/hooks/useSyllabusStream";
import { useSyllabusStore } from "@/hooks/useSyllabusStore";
import { useThreadsSWR } from "@/hooks/useThreadsSWR";
import { cn } from "@/lib/cn";
import { Menu, X, AlertTriangle } from "lucide-react";

export function AppShell() {
  const [threadId, setThreadId] = useQueryState("thread");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const { mutate: refreshThreads } = useThreadsSWR();

  const handleMissingThread = useCallback(() => {
    setToast("That thread no longer exists. Starting fresh.");
    setThreadId(null);
  }, [setThreadId]);

  const { stream, progress, resetProgress } = useSyllabusStream(
    threadId ?? undefined,
    handleMissingThread,
  );
  const store = useSyllabusStore(threadId ?? undefined);

  // When useStream auto-creates a thread, sync its id into the URL.
  useEffect(() => {
    const s = stream as any;
    const created = s?.thread?.thread_id ?? s?.threadId ?? s?.values?._thread_id;
    if (!threadId && created) {
      setThreadId(created);
      refreshThreads();
    }
  }, [stream, threadId, setThreadId, refreshThreads]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  const submitNewSyllabus = useCallback(async (requirements: string) => {
    try {
      await stream.submit(
        { requirements },
        { streamMode: ["values", "messages-tuple", "custom"] }
      );
    } catch (e) { console.error(e); setToast("Could not start the thread. Check the agent URL."); }
  }, [stream]);

  const inLanding = !threadId;

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

      {/* Sidebar (drawer on mobile, persistent on md+) */}
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

      {toast && (
        <div className="fixed bottom-4 left-1/2 z-40 -translate-x-1/2 rounded-xl border border-warn/40 bg-warn-soft dark:bg-warn/10 px-3 py-2 text-xs text-warn shadow-md flex items-center gap-2">
          <AlertTriangle className="h-3.5 w-3.5" /> {toast}
        </div>
      )}

      {inLanding ? (
        <main className="min-h-0 flex-1 overflow-y-auto">
          <HeroLanding onSubmit={submitNewSyllabus} disabled={Boolean(stream?.isLoading)} />
        </main>
      ) : (
        <main className="flex min-h-0 flex-1 flex-col md:flex-row">
          <section className="min-h-0 flex-1 overflow-y-auto border-b border-border dark:border-border-dark md:border-b-0 md:border-r">
            <CenterPlan store={store} progress={progress} threadId={threadId ?? undefined} />
          </section>
          <section className="min-h-0 w-full shrink-0 md:w-[380px] lg:w-[420px]">
            <AgentPane
              stream={stream}
              progress={progress}
              threadId={threadId ?? undefined}
            />
          </section>
        </main>
      )}
    </div>
  );
}
