"use client";
/**
 * LessonMarkdownViewer — renders a lesson's `content_markdown` as styled
 * Markdown with GFM + syntax-highlighted code blocks.
 *
 * Replaces the previous BlockNote editor. The MPFE agent writes Markdown
 * directly (via exec_commit_lesson → lessons.content_markdown), so the
 * frontend is a read-only view. When the lesson row updates in Supabase
 * Realtime, this component rerenders automatically because the parent
 * keys it on `lesson.id` + `lesson.updated_at`.
 */
import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";
import type { Lesson } from "@/store/syllabusStore";
import { BookOpen, Loader2 } from "lucide-react";

interface Props {
  lesson: Lesson;
}

function LessonMarkdownViewerImpl({ lesson }: Props) {
  const md = (lesson.content_markdown ?? "").trim();

  if (!md) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center gap-3 text-[var(--muted-foreground)]">
        <Loader2 className="h-6 w-6 animate-spin" />
        <div className="text-sm">
          Lesson <span className="font-mono">{lesson.title || lesson.id.slice(0, 8)}</span> is being written…
        </div>
      </div>
    );
  }

  return (
    <div className="h-full w-full overflow-y-auto bg-background">
      <div className="mx-auto w-full max-w-3xl px-6 py-8">
        <header className="mb-6 border-b border-[var(--border)] pb-4">
          <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-[var(--muted-foreground)]">
            <BookOpen className="h-3.5 w-3.5" />
            <span>Lesson</span>
            {lesson.needs_review ? (
              <span className="ml-2 rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">
                needs review
              </span>
            ) : null}
          </div>
          <h1 className="mt-1 text-2xl font-semibold text-foreground">{lesson.title}</h1>
        </header>
        <article className="prose prose-invert max-w-none text-[15px] leading-relaxed">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
          >
            {md}
          </ReactMarkdown>
        </article>
      </div>
    </div>
  );
}

export const LessonMarkdownViewer = memo(LessonMarkdownViewerImpl);

export function EmptyViewerState() {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-3 text-[var(--muted-foreground)]">
      <BookOpen className="h-10 w-10 opacity-40" />
      <div className="max-w-xs text-center text-sm">
        Select a lesson or activity from the file tree.
      </div>
    </div>
  );
}
