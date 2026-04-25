"use client";
/**
 * FileTree — left sidebar rendering the live curriculum for the current
 * thread. Data is fed by `useSyllabusRealtime` (subscribed at the top of
 * the viewer) and appears in the tree immediately as each Supabase row
 * lands (agent-written).
 *
 * Hierarchy: Syllabus > Chapter > (Lessons + Activities).
 * Clicking a lesson or activity sets the active item; the viewer pane
 * renders the right component.
 */
import { useEffect } from "react";
import {
  useSyllabusStore,
  type Chapter,
  type Lesson,
  type Activity,
} from "@/store/syllabusStore";
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  FileText,
  FolderOpen,
  Loader2,
} from "lucide-react";

export function FileTree() {
  const syllabus = useSyllabusStore((s) => s.syllabus);
  const chapters = useSyllabusStore((s) => s.chapters);
  const lessons = useSyllabusStore((s) => s.lessons);
  const activities = useSyllabusStore((s) => s.activities);
  const activeItemId = useSyllabusStore((s) => s.activeItemId);
  const expanded = useSyllabusStore((s) => s.expandedChapterIds);
  const toggleChapter = useSyllabusStore((s) => s.toggleChapter);
  const setActiveItem = useSyllabusStore((s) => s.setActiveItem);

  // Auto-expand chapters as they arrive (the first time we see them)
  useEffect(() => {
    for (const c of chapters) {
      if (!expanded.has(c.id)) {
        toggleChapter(c.id);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapters.length]);

  if (!syllabus) {
    return (
      <aside className="flex h-full flex-col border-r border-[var(--border)] bg-[var(--card)]/60">
        <TreeHeader />
        <div className="flex flex-1 items-center justify-center p-6 text-xs text-[var(--muted-foreground)]">
          <div className="flex flex-col items-center gap-2 text-center">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Waiting for the agent to start a syllabus…</span>
          </div>
        </div>
      </aside>
    );
  }

  return (
    <aside className="flex h-full flex-col border-r border-[var(--border)] bg-[var(--card)]/60">
      <TreeHeader title={syllabus.title} />
      <div className="flex-1 overflow-y-auto px-1 pb-4">
        <ul className="mt-1 flex flex-col">
          {chapters.map((c) => (
            <ChapterNode
              key={c.id}
              chapter={c}
              lessons={lessons.filter((l) => l.chapter_id === c.id)}
              activities={activities.filter((a) => a.chapter_id === c.id)}
              expanded={expanded.has(c.id)}
              activeItemId={activeItemId}
              onToggle={() => toggleChapter(c.id)}
              onSelect={setActiveItem}
            />
          ))}
          {chapters.length === 0 ? (
            <li className="px-3 py-2 text-[11px] text-[var(--muted-foreground)]">
              No chapters yet…
            </li>
          ) : null}
        </ul>
      </div>
    </aside>
  );
}

function TreeHeader({ title }: { title?: string }) {
  return (
    <header className="flex shrink-0 items-center gap-2 border-b border-[var(--border)] px-3 py-2 text-xs font-semibold text-[var(--foreground)]">
      <FolderOpen className="h-3.5 w-3.5 text-[var(--primary)]" />
      <span className="truncate">{title ?? "Syllabus"}</span>
    </header>
  );
}

interface ChapterNodeProps {
  chapter: Chapter;
  lessons: Lesson[];
  activities: Activity[];
  expanded: boolean;
  activeItemId: string | null;
  onToggle: () => void;
  onSelect: (id: string) => void;
}

function ChapterNode({
  chapter,
  lessons,
  activities,
  expanded,
  activeItemId,
  onToggle,
  onSelect,
}: ChapterNodeProps) {
  const count = lessons.length + activities.length;
  return (
    <li className="flex flex-col">
      <button
        type="button"
        onClick={onToggle}
        className="group flex items-center gap-1 rounded px-2 py-1 text-left text-[13px] font-medium text-[var(--foreground)] hover:bg-[var(--accent)]"
      >
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
        )}
        <span className="mr-1 font-mono text-[10px] text-[var(--muted-foreground)]">
          #{chapter.position}
        </span>
        <span className="flex-1 truncate">{chapter.title || "Untitled chapter"}</span>
        <span className="rounded bg-[var(--muted)] px-1.5 py-0.5 text-[10px] text-[var(--muted-foreground)]">
          {count}
        </span>
      </button>
      {expanded ? (
        <ul className="ml-4 border-l border-[var(--border)] pl-2">
          {lessons.map((l) => (
            <LeafNode
              key={l.id}
              id={l.id}
              label={l.title || `Lesson ${l.position}`}
              icon="lesson"
              active={l.id === activeItemId}
              dim={!l.content_markdown}
              onSelect={onSelect}
            />
          ))}
          {activities.map((a) => (
            <LeafNode
              key={a.id}
              id={a.id}
              label={a.title || `Activity ${a.position}`}
              icon="activity"
              active={a.id === activeItemId}
              dim={!a.payload?.questions?.length}
              onSelect={onSelect}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

interface LeafProps {
  id: string;
  label: string;
  icon: "lesson" | "activity";
  active: boolean;
  dim: boolean;
  onSelect: (id: string) => void;
}

function LeafNode({ id, label, icon, active, dim, onSelect }: LeafProps) {
  const Icon = icon === "lesson" ? FileText : ClipboardCheck;
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(id)}
        className={
          "flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-[12.5px] " +
          (active
            ? "bg-[var(--primary)]/20 text-[var(--primary-foreground)]"
            : "text-[var(--foreground)] hover:bg-[var(--accent)]")
        }
      >
        <Icon
          className={
            "h-3.5 w-3.5 " +
            (icon === "activity"
              ? "text-amber-400"
              : dim
                ? "text-[var(--muted-foreground)]"
                : "text-sky-400")
          }
        />
        <span className={"flex-1 truncate " + (dim ? "italic opacity-70" : "")}>{label}</span>
      </button>
    </li>
  );
}
