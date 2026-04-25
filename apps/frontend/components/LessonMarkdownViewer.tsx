"use client";
/**
 * LessonMarkdownViewer — classroom-grade typography for a lesson's
 * `content_markdown`. Uses @tailwindcss/typography + custom component
 * overrides to give large, airy headings, pretty code blocks with a
 * language tag + copy button, styled blockquotes as callouts, real
 * table styling, and generous vertical rhythm.
 */
import { memo, useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";
import type { Lesson } from "@/store/syllabusStore";
import { BookOpen, Clock, Copy, Check, Loader2 } from "lucide-react";

interface Props {
  lesson: Lesson;
}

function fmtUpdated(ts?: string | null): string | null {
  if (!ts) return null;
  try {
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return null;
  }
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          /* ignore */
        }
      }}
      className="inline-flex items-center gap-1 rounded-md border border-[var(--border)] bg-[var(--card)] px-2 py-1 text-[11px] font-medium text-[var(--muted-foreground)] opacity-0 transition hover:text-foreground group-hover:opacity-100"
      aria-label="Copy code"
    >
      {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function extractText(node: any): string {
  if (node == null) return "";
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (typeof node === "object" && "props" in node && node.props?.children) {
    return extractText(node.props.children);
  }
  return "";
}

const mdComponents: Components = {
  h1: ({ children }) => (
    <h1 className="mt-10 mb-4 scroll-mt-20 border-b border-[var(--border)] pb-3 text-[28px] font-bold leading-tight tracking-tight text-foreground first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mt-10 mb-3 scroll-mt-20 border-b border-[var(--border)]/60 pb-2 text-[22px] font-semibold leading-tight tracking-tight text-foreground first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-7 mb-2 scroll-mt-20 text-[18px] font-semibold leading-snug text-foreground">
      {children}
    </h3>
  ),
  h4: ({ children }) => (
    <h4 className="mt-5 mb-2 text-[15px] font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">
      {children}
    </h4>
  ),
  p: ({ children }) => (
    <p className="my-4 text-[15.5px] leading-[1.75] text-foreground/90">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="my-4 list-disc space-y-1.5 pl-6 text-[15.5px] leading-[1.75] marker:text-[var(--primary)]">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="my-4 list-decimal space-y-1.5 pl-6 text-[15.5px] leading-[1.75] marker:font-semibold marker:text-[var(--primary)]">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="pl-1 [&>p]:my-0">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="my-5 rounded-r-md border-l-4 border-[var(--secondary)] bg-[var(--secondary)]/10 px-4 py-3 text-[15px] italic text-foreground/90">
      {children}
    </blockquote>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-[var(--primary)] underline decoration-[var(--primary)]/40 decoration-2 underline-offset-2 transition hover:decoration-[var(--primary)]"
    >
      {children}
    </a>
  ),
  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
  em: ({ children }) => <em className="italic text-foreground/90">{children}</em>,
  hr: () => <hr className="my-8 border-t border-[var(--border)]" />,
  table: ({ children }) => (
    <div className="my-5 overflow-x-auto rounded-lg border border-[var(--border)]">
      <table className="w-full border-collapse text-[14px]">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-[var(--muted)]/60">{children}</thead>,
  th: ({ children }) => (
    <th className="border-b border-[var(--border)] px-3 py-2 text-left font-semibold">{children}</th>
  ),
  td: ({ children }) => (
    <td className="border-b border-[var(--border)]/40 px-3 py-2 align-top">{children}</td>
  ),
  code: ({ className, children, ...props }) => {
    const isBlock = /language-/.test(className ?? "");
    if (!isBlock) {
      return (
        <code
          className="rounded-md border border-[var(--border)] bg-[var(--muted)] px-1.5 py-0.5 font-mono text-[13px] text-[var(--secondary)]"
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
  pre: ({ children }) => {
    // Extract language from nested <code className="language-xxx">
    const child = Array.isArray(children) ? children[0] : children;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const codeProps = (child as any)?.props ?? {};
    const className: string = codeProps.className ?? "";
    const lang = (className.match(/language-(\w+)/) ?? [])[1] ?? "code";
    const raw = extractText(children);
    return (
      <div className="group relative my-5 overflow-hidden rounded-lg border border-[var(--border)] bg-[#0d1117]">
        <div className="flex items-center justify-between border-b border-[var(--border)] bg-[#161b22] px-3 py-1.5">
          <span className="font-mono text-[11px] uppercase tracking-wide text-[var(--muted-foreground)]">
            {lang}
          </span>
          <CopyButton text={raw} />
        </div>
        <pre className="overflow-x-auto p-4 text-[13.5px] leading-[1.6]">{children as ReactNode}</pre>
      </div>
    );
  },
};

function LessonMarkdownViewerImpl({ lesson }: Props) {
  const md = (lesson.content_markdown ?? "").trim();
  const updated = fmtUpdated(lesson.updated_at);

  if (!md) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center gap-3 text-[var(--muted-foreground)]">
        <Loader2 className="h-6 w-6 animate-spin" />
        <div className="text-sm">
          Lesson <span className="font-mono">{lesson.title || lesson.id.slice(0, 8)}</span> is being
          written…
        </div>
      </div>
    );
  }

  return (
    <div className="h-full w-full overflow-y-auto bg-background">
      <div className="mx-auto w-full max-w-3xl px-8 py-10">
        <header className="mb-8 border-b border-[var(--border)] pb-6">
          <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.15em] text-[var(--primary)]">
            <BookOpen className="h-3.5 w-3.5" />
            <span>Lesson</span>
            {lesson.needs_review ? (
              <span className="ml-2 rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-semibold normal-case tracking-normal text-amber-300">
                needs review
              </span>
            ) : null}
          </div>
          <h1 className="mt-2 text-[32px] font-bold leading-tight tracking-tight text-foreground">
            {lesson.title}
          </h1>
          {updated ? (
            <div className="mt-3 flex items-center gap-1.5 text-[12px] text-[var(--muted-foreground)]">
              <Clock className="h-3 w-3" />
              Updated {updated}
            </div>
          ) : null}
        </header>
        <article className="lesson-article">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
            components={mdComponents}
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
