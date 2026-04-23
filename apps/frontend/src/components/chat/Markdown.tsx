"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Minimal markdown renderer with project styling. Safe default (no rehype-raw). */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="prose-chat">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node, ...props }) => (
            <a {...props} target="_blank" rel="noreferrer noopener" className="underline decoration-dotted underline-offset-2 hover:text-fg dark:hover:text-fg-dark" />
          ),
          code: ({ node, className, children, ...props }: any) => {
            const inline = !String(className || "").includes("language-");
            if (inline) {
              return <code className="rounded bg-accent-soft dark:bg-fg-dark/10 px-1 py-0.5 text-[0.85em] font-mono" {...props}>{children}</code>;
            }
            return (
              <pre className="overflow-x-auto rounded-xl bg-accent-soft dark:bg-fg-dark/10 p-3 text-xs font-mono leading-relaxed">
                <code {...props}>{children}</code>
              </pre>
            );
          },
          ul: ({ node, ...props }) => <ul className="list-disc space-y-1 pl-5" {...props} />,
          ol: ({ node, ...props }) => <ol className="list-decimal space-y-1 pl-5" {...props} />,
          h1: ({ node, ...props }) => <h1 className="mt-2 mb-1 text-base font-semibold" {...props} />,
          h2: ({ node, ...props }) => <h2 className="mt-2 mb-1 text-[0.95rem] font-semibold" {...props} />,
          h3: ({ node, ...props }) => <h3 className="mt-2 mb-1 text-sm font-semibold" {...props} />,
          p:  ({ node, ...props }) => <p className="leading-relaxed" {...props} />,
          blockquote: ({ node, ...props }) => (
            <blockquote className="border-l-2 border-border dark:border-border-dark pl-3 text-fg-muted" {...props} />
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
