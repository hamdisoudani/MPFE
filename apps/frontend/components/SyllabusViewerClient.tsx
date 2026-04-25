"use client";
/**
 * SyllabusViewerClient — the three-pane shell:
 *   [File tree | Lesson/Activity viewer | Chat pane]
 *
 * The viewer pane switches between:
 *   - <LessonMarkdownViewer>  (when an active item is a lesson)
 *   - <ChapterQuiz>           (when an active item is an activity)
 *   - <EmptyViewerState>      (otherwise)
 *
 * `useSyllabusRealtime` is mounted here so the tree updates live as soon
 * as the agent inserts chapters / lessons / activities in Supabase.
 */
import { useEffect, useState } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { FolderTree, MessageSquare, NotebookPen, ListTree } from "lucide-react";
import { useSyllabusStore } from "@/store/syllabusStore";
import { useSyllabusRealtime } from "@/hooks/useSyllabusRealtime";
import { ActiveThreadsRealtime } from "@/hooks/useActiveThreadsRealtime";
import { useThreads } from "@/providers/Thread";
import { useQueryState } from "nuqs";
import { FileTree } from "@/components/FileTree";
import { LessonMarkdownViewer, EmptyViewerState } from "@/components/LessonMarkdownViewer";
import ChapterQuiz from "@/components/ChapterQuiz";
import { ChatPane } from "@/components/chat/ChatPane";
import { ThreadHistory } from "@/components/chat/ThreadHistory";
import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { SiteHeader } from "@/components/layout/SiteHeader";

type MobileTab = "threads" | "files" | "editor" | "chat";

const TABS: { id: MobileTab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "threads", label: "Threads", icon: ListTree },
  { id: "files", label: "Files", icon: FolderTree },
  { id: "editor", label: "Editor", icon: NotebookPen },
  { id: "chat", label: "Chat", icon: MessageSquare },
];

function useIsDesktop() {
  const [isDesktop, setIsDesktop] = useState(true);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const apply = () => setIsDesktop(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);
  return isDesktop;
}

export default function SyllabusViewerClient() {
  const [threadId] = useQueryState("threadId");
  useSyllabusRealtime(threadId);
  const activeLesson = useSyllabusStore((s) => s.getActiveLesson());
  const activeActivity = useSyllabusStore((s) => s.getActiveActivity());
  const isDesktop = useIsDesktop();
  const [tab, setTab] = useState<MobileTab>("chat");

  const viewerPane = activeLesson ? (
    <LessonMarkdownViewer
      key={`${activeLesson.id}:${activeLesson.content_markdown?.length ?? 0}`}
      lesson={activeLesson}
    />
  ) : activeActivity ? (
    <ChapterQuiz key={activeActivity.id} activity={activeActivity} />
  ) : (
    <EmptyViewerState />
  );

  const realtimeBoot = <ActiveThreadsRealtime limit={5} />;

  if (isDesktop) {
    return (
      <>
        {realtimeBoot}
        <SidebarProvider
          style={{ "--sidebar-width": "16rem", "--header-height": "3rem" } as React.CSSProperties}
        >
          <AppSidebar />
          <SidebarInset className="h-screen overflow-hidden">
            <SiteHeader />
            <div className="flex-1 min-h-0">
              <PanelGroup direction="horizontal" className="h-full w-full bg-background text-foreground">
                <Panel defaultSize={22} minSize={14}>
                  <FileTree />
                </Panel>
                <PanelResizeHandle className="w-px bg-[var(--border)] hover:bg-[var(--primary)] transition-colors" />
                <Panel defaultSize={48} minSize={25}>
                  {viewerPane}
                </Panel>
                <PanelResizeHandle className="w-px bg-[var(--border)] hover:bg-[var(--primary)] transition-colors" />
                <Panel defaultSize={30} minSize={18}>
                  <ChatPane />
                </Panel>
              </PanelGroup>
            </div>
          </SidebarInset>
        </SidebarProvider>
      </>
    );
  }

  return (
    <>
      {realtimeBoot}
      <div className="flex h-full w-full flex-col bg-background text-foreground">
        <div className="flex-1 min-h-0 relative">
          <div className={`absolute inset-0 ${tab === "threads" ? "block" : "hidden"}`}><ThreadHistory /></div>
          <div className={`absolute inset-0 ${tab === "files" ? "block" : "hidden"}`}><FileTree /></div>
          <div className={`absolute inset-0 ${tab === "editor" ? "block" : "hidden"}`}>{viewerPane}</div>
          <div className={`absolute inset-0 ${tab === "chat" ? "block" : "hidden"}`}><ChatPane /></div>
        </div>
        <nav className="flex shrink-0 border-t border-[var(--border)] bg-[var(--card)]" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
          {TABS.map(({ id, label, icon: Icon }) => {
            const active = tab === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                aria-pressed={active}
                className={`flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[10px] transition-colors ${
                  active
                    ? "text-[var(--primary)] bg-[var(--accent)]"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </>
  );
}
