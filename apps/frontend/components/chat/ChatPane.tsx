"use client";
/**
 * ChatPane — MPFE supervisor-agent chat UI.
 *
 * Responsibilities:
 *   • Maintain an `useStream` connection to the syllabus agent (langgraph-sdk).
 *   • Render the running message transcript (user + assistant Markdown).
 *   • Show the agent's native `interrupt({question, tool_call_id})` as an
 *     "Agent is asking…" card with a text input; submit answers via
 *     `stream.submit(undefined, {command: {resume: <answer>}})`.
 *   • Render the live Search Plan + Todo Plan (from stream state values) so
 *     the user can watch multi-step progress as it happens.
 *   • Offer a composer to send a new user message, a Stop button to cancel
 *     the current run, and a subtle phase badge.
 *
 * The previous MASTER-PFE ChatPane is preserved as ChatPane.legacy.tsx — it
 * was built for a different agent contract (frontend_tool_call interrupts,
 * BlockNote block schemas, MCP tools, subagent subtasks). None of that
 * applies to MPFE.
 */
import React, {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useQueryState } from "nuqs";
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleDashed,
  Compass,
  ListTodo,
  Loader2,
  Pause,
  Pencil,
  Play,
  Send,
  Sparkles,
  Square,
  User as UserIcon,
  Wand2,
} from "lucide-react";
import { useSyllabusAgent } from "@/lib/useSyllabusAgent";
import { Markdown } from "@/components/chat/Markdown";
import { useThreadMessagesCache } from "@/stores/thread-messages-cache";

// ─── Types ─────────────────────────────────────────────────────────────────
interface AgentMessage {
  id?: string;
  type?: string;
  role?: string;
  content?: unknown;
  tool_calls?: { name?: string; args?: unknown; id?: string }[];
  tool_call_id?: string;
  name?: string;
}

interface SearchStepV {
  id: string;
  title: string;
  queries: string[];
  status: "pending" | "searching" | "scraping" | "done";
}

interface SearchPlanV {
  global_goal: string;
  steps: SearchStepV[];
}

interface TodoStepV {
  id: string;
  chapter_ref: string;
  name: string;
  kind?: "lesson" | "activity";
  description?: string;
  must_cover?: string[];
  depends_on?: string[];
  status:
    | "pending"
    | "writing"
    | "critiquing"
    | "accepted"
    | "rejected"
    | "failed";
  attempts?: number;
}

interface TodoPlanV {
  steps: TodoStepV[];
}

interface InterruptShape {
  question: string;
  tool_call_id?: string;
}

// ─── Helpers ───────────────────────────────────────────────────────────────
function extractText(c: unknown): string {
  if (c == null) return "";
  if (typeof c === "string") return c;
  if (Array.isArray(c)) {
    return c
      .map((p) =>
        typeof p === "string"
          ? p
          : typeof p === "object" && p && "text" in p
            ? String((p as { text?: unknown }).text ?? "")
            : "",
      )
      .join("");
  }
  return "";
}

function mapMessage(m: AgentMessage): {
  id: string;
  role: "user" | "assistant" | "tool" | "system";
  text: string;
  toolCalls: { name: string; args: unknown }[];
  toolCallName?: string;
} {
  const role =
    m.role === "user" || m.type === "human"
      ? ("user" as const)
      : m.role === "assistant" || m.type === "ai"
        ? ("assistant" as const)
        : m.role === "tool" || m.type === "tool"
          ? ("tool" as const)
          : ("system" as const);
  return {
    id: m.id ?? Math.random().toString(36).slice(2),
    role,
    text: extractText(m.content),
    toolCalls: Array.isArray(m.tool_calls)
      ? m.tool_calls.map((tc) => ({ name: tc?.name ?? "?", args: tc?.args }))
      : [],
    toolCallName: m.name,
  };
}

// ─── Plan renderers ────────────────────────────────────────────────────────
const STEP_DOT = {
  pending: "bg-[var(--muted-foreground)]/40",
  searching: "bg-[var(--secondary)] animate-pulse",
  scraping: "bg-[var(--secondary)] animate-pulse",
  done: "bg-emerald-500",
  writing: "bg-[var(--secondary)] animate-pulse",
  critiquing: "bg-[var(--primary)] animate-pulse",
  accepted: "bg-emerald-500",
  rejected: "bg-amber-500",
  failed: "bg-[var(--destructive)]",
} as Record<string, string>;

function StepDot({ status }: { status: string }) {
  return (
    <span
      aria-hidden
      className={`mt-[7px] h-2 w-2 shrink-0 rounded-full ${STEP_DOT[status] ?? STEP_DOT.pending}`}
    />
  );
}

function SearchPlanCard({ plan }: { plan: SearchPlanV }) {
  const [open, setOpen] = useState(true);
  const total = plan.steps.length;
  const done = plan.steps.filter((s) => s.status === "done").length;
  return (
    <section className="mb-3 rounded-md border border-[var(--border)] bg-[var(--card)]/80 text-[13px]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        <Compass className="h-3.5 w-3.5 text-[var(--secondary)]" />
        <span className="font-semibold">Research plan</span>
        <span className="text-[11px] text-[var(--muted-foreground)]">
          {done}/{total}
        </span>
        <span className="ml-auto text-[var(--muted-foreground)]">
          {open ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
        </span>
      </button>
      {open ? (
        <div className="border-t border-[var(--border)] px-3 py-2">
          {plan.global_goal ? (
            <p className="mb-2 text-[12px] italic text-[var(--muted-foreground)]">
              Goal: {plan.global_goal}
            </p>
          ) : null}
          <ol className="space-y-1.5">
            {plan.steps.map((s) => (
              <li key={s.id} className="flex items-start gap-2">
                <StepDot status={s.status} />
                <div className="flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-[11px] text-[var(--muted-foreground)]">
                      {s.id}
                    </span>
                    <span className="text-[13px]">{s.title}</span>
                    <span className="ml-auto text-[11px] capitalize text-[var(--muted-foreground)]">
                      {s.status}
                    </span>
                  </div>
                  {s.queries?.length ? (
                    <ul className="mt-0.5 space-y-0.5 pl-2 text-[11px] text-[var(--muted-foreground)]">
                      {s.queries.slice(0, 3).map((q, i) => (
                        <li key={i} className="truncate">
                          › {q}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}

function TodoPlanCard({ plan }: { plan: TodoPlanV }) {
  const [open, setOpen] = useState(true);
  const total = plan.steps.length;
  const done = plan.steps.filter(
    (s) => s.status === "accepted" || s.status === "failed",
  ).length;
  return (
    <section className="mb-3 rounded-md border border-[var(--border)] bg-[var(--card)]/80 text-[13px]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        <ListTodo className="h-3.5 w-3.5 text-[var(--primary)]" />
        <span className="font-semibold">Working plan</span>
        <span className="text-[11px] text-[var(--muted-foreground)]">
          {done}/{total}
        </span>
        <span className="ml-auto text-[var(--muted-foreground)]">
          {open ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
        </span>
      </button>
      {open ? (
        <div className="border-t border-[var(--border)] px-3 py-2">
          <ol className="space-y-1.5">
            {plan.steps.map((s) => (
              <li key={s.id} className="flex items-start gap-2">
                <StepDot status={s.status} />
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-mono text-[11px] text-[var(--muted-foreground)]">
                      {s.id}
                    </span>
                    <span className="rounded bg-[var(--muted)] px-1 py-px font-mono text-[10px] text-[var(--muted-foreground)]">
                      {s.chapter_ref}
                    </span>
                    <span
                      className={`rounded px-1 py-px text-[10px] font-semibold uppercase ${
                        s.kind === "activity"
                          ? "bg-amber-500/20 text-amber-300"
                          : "bg-sky-500/20 text-sky-300"
                      }`}
                    >
                      {s.kind ?? "lesson"}
                    </span>
                    <span className="text-[13px]">{s.name}</span>
                    <span className="ml-auto text-[11px] capitalize text-[var(--muted-foreground)]">
                      {s.status}
                      {s.attempts ? ` · a${s.attempts}` : null}
                    </span>
                  </div>
                  {s.depends_on?.length ? (
                    <div className="mt-0.5 text-[11px] text-[var(--muted-foreground)]">
                      depends on:{" "}
                      {s.depends_on.map((d) => (
                        <span
                          key={d}
                          className="mr-1 rounded bg-[var(--muted)] px-1 py-px font-mono text-[10px]"
                        >
                          {d}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}

// ─── Interrupt card: text-input answer to agent's ask_user ────────────────
function InterruptCard({
  question,
  onSubmit,
  busy,
}: {
  question: string;
  onSubmit: (answer: string) => void;
  busy: boolean;
}) {
  const [val, setVal] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    ref.current?.focus();
  }, []);
  const canSubmit = val.trim().length > 0 && !busy;
  const submit = () => {
    if (!canSubmit) return;
    onSubmit(val.trim());
    setVal("");
  };
  return (
    <div className="mb-3 rounded-lg border border-[var(--primary)]/40 bg-[var(--primary)]/10 p-3">
      <div className="mb-2 flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wide text-[var(--primary)]">
        <Wand2 className="h-3.5 w-3.5" /> Agent needs your input
      </div>
      <p className="mb-3 whitespace-pre-wrap text-[14px] text-foreground">
        {question}
      </p>
      <textarea
        ref={ref}
        value={val}
        onChange={(e) => setVal(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
        }}
        rows={3}
        placeholder="Type your answer… (⌘/Ctrl+Enter to submit)"
        className="w-full resize-y rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-[14px] outline-none focus:border-[var(--primary)]"
      />
      <div className="mt-2 flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={submit}
          disabled={!canSubmit}
          className="inline-flex items-center gap-1 rounded-md bg-[var(--primary)] px-3 py-1.5 text-[13px] font-semibold text-[var(--primary-foreground)] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Send className="h-3.5 w-3.5" />
          )}
          Send answer
        </button>
      </div>
    </div>
  );
}

// Tools that have first-class in-chat UI (plans, FileTree, interrupt card).
// Don't show a "calling X…" chip for these — the UI already illustrates them.
const SUPPRESSED_TOOL_CALL_NAMES = new Set([
  "set_search_plan",
  "set_todo_plan",
  "create_syllabus",
  "create_chapters",
  "list_thread_syllabi",
  "ask_user",
]);

// ─── Message bubble ────────────────────────────────────────────────────────
const MessageBubble = memo(function MessageBubble({
  m,
}: {
  m: ReturnType<typeof mapMessage>;
}) {
  if (m.role === "tool") return null; // tool results are internal; hide
  const isUser = m.role === "user";
  const label = isUser ? "You" : "Agent";
  const Icon = isUser ? UserIcon : Bot;
  const hasToolCalls = m.toolCalls.length > 0;
  // Suppress bare tool-call-only bubbles w/ empty text — plans / FileTree / interrupt
  // cards already illustrate these transitions; a floating "calling X…" chip is noise.
  if (!isUser && !m.text && hasToolCalls) {
    const visible = m.toolCalls.filter(
      (tc) => tc.name && !SUPPRESSED_TOOL_CALL_NAMES.has(tc.name),
    );
    if (visible.length === 0) return null;
    return (
      <div className="mb-3 flex items-start gap-2 text-[12px] text-[var(--muted-foreground)]">
        <Sparkles className="mt-0.5 h-3 w-3 text-[var(--primary)]" />
        <div className="italic">
          calling{" "}
          {visible
            .map((tc) => <span key={tc.name} className="font-mono">{tc.name}</span>)
            .reduce((prev: React.ReactNode[], cur, i) => {
              if (i === 0) return [cur];
              return [...prev, ", ", cur];
            }, [])}
          …
        </div>
      </div>
    );
  }
  return (
    <div
      className={`mb-3 flex items-start gap-2 ${isUser ? "flex-row-reverse" : ""}`}
    >
      <div
        className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
          isUser
            ? "bg-[var(--primary)]/20 text-[var(--primary)]"
            : "bg-[var(--secondary)]/20 text-[var(--secondary)]"
        }`}
      >
        <Icon className="h-3.5 w-3.5" />
      </div>
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-[14px] ${
          isUser
            ? "bg-[var(--primary)]/15 text-foreground"
            : "bg-[var(--card)] text-foreground"
        }`}
      >
        <div className="mb-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">
          {label}
        </div>
        {m.text ? <Markdown source={m.text} /> : null}
      </div>
    </div>
  );
});

// ─── Phase badge ───────────────────────────────────────────────────────────
function PhaseBadge({ phase, streaming }: { phase?: string; streaming: boolean }) {
  const show = streaming || (phase && phase !== "idle" && phase !== "done");
  if (!show) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-[var(--border)] bg-[var(--muted)]/70 px-2 py-0.5 text-[10px] uppercase tracking-wide text-[var(--muted-foreground)]">
      {streaming ? (
        <Loader2 className="h-2.5 w-2.5 animate-spin" />
      ) : (
        <CircleDashed className="h-2.5 w-2.5" />
      )}
      {phase ?? "streaming"}
    </span>
  );
}

// ─── Main ──────────────────────────────────────────────────────────────────
export function ChatPane() {
  const [threadId, setThreadId] = useQueryState("threadId");

  const stream = useSyllabusAgent({
    threadId,
    onThreadId: (id) => {
      if (id && id !== threadId) void setThreadId(id);
    },
  }) as ReturnType<typeof useSyllabusAgent> & {
    interrupt?: { value?: unknown };
    values?: Record<string, unknown>;
    isLoading?: boolean;
    error?: unknown;
    stop?: () => void;
    submit?: (
      input: unknown,
      opts?: Record<string, unknown>,
    ) => void;
  };

  const messagesRaw = (stream.messages ?? []) as AgentMessage[];
  const messages = useMemo(() => messagesRaw.map(mapMessage), [messagesRaw]);

  // Seed the per-thread message cache so warm reloads can repaint the
  // transcript from localStorage before/while SSE reconnects. Throttled by
  // messages.length to avoid writing on every token delta.
  const cacheSet = useThreadMessagesCache((s) => s.set);
  useEffect(() => {
    if (!threadId || messagesRaw.length === 0) return;
    cacheSet(threadId, messagesRaw);
  }, [threadId, messagesRaw.length, cacheSet, messagesRaw]);
  const values = (stream.values ?? {}) as Record<string, unknown>;
  const phase = typeof values.phase === "string" ? (values.phase as string) : undefined;
  const searchPlan = values.search_plan as SearchPlanV | null | undefined;
  const todoPlan = values.todo_plan as TodoPlanV | null | undefined;

  const interruptValue = stream.interrupt?.value as
    | InterruptShape
    | null
    | undefined;
  const hasInterrupt =
    !!interruptValue &&
    typeof interruptValue === "object" &&
    typeof interruptValue.question === "string";

  const isStreaming = !!stream.isLoading && !hasInterrupt;

  const [composerText, setComposerText] = useState("");

  // Auto-scroll
  const scrollRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const stickyRef = useRef(true);
  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const dist = el.scrollHeight - (el.scrollTop + el.clientHeight);
    stickyRef.current = dist < 160;
  }, []);
  useEffect(() => {
    if (!stickyRef.current) return;
    const id = requestAnimationFrame(() =>
      endRef.current?.scrollIntoView({ block: "end" }),
    );
    return () => cancelAnimationFrame(id);
  }, [messages.length, isStreaming, hasInterrupt]);

  // ─── Handlers ────────────────────────────────────────────────────────────
  // The SDK's useStream auto-creates a thread on submit when threadId is
  // null/undefined and fires `onThreadId` with the new id (we wire that to
  // the URL above). So we don't create one manually — doing so raced with
  // the stream hook rebinding to the new id and caused the very first send
  // to be orphaned (message never rendered because the submit went against
  // a stream bound to the old `threadId=null`).
  const submitUserMessage = useCallback(
    (text: string) => {
      stickyRef.current = true;
      stream.submit?.(
        { messages: [{ role: "user", content: text }] },
        { streamSubgraphs: true },
      );
    },
    [stream],
  );

  const answerInterrupt = useCallback(
    (answer: string) => {
      if (!hasInterrupt) return;
      stream.submit?.(undefined, {
        command: { resume: answer },
        streamSubgraphs: true,
      });
    },
    [hasInterrupt, stream],
  );

  const onStop = useCallback(() => {
    try {
      stream.stop?.();
    } catch {
      /* ignore */
    }
  }, [stream]);

  const onSendKey = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        const v = composerText.trim();
        if (!v || isStreaming) return;
        setComposerText("");
        submitUserMessage(v);
      }
    },
    [composerText, isStreaming, submitUserMessage],
  );

  const onSendClick = useCallback(() => {
    const v = composerText.trim();
    if (!v || isStreaming) return;
    setComposerText("");
    submitUserMessage(v);
  }, [composerText, isStreaming, submitUserMessage]);

  const errorText =
    stream.error && typeof stream.error === "object" && "message" in stream.error
      ? String((stream.error as { message?: unknown }).message ?? "")
      : stream.error
        ? String(stream.error)
        : null;

  const emptyState = messages.length === 0 && !hasInterrupt && !searchPlan && !todoPlan;

  return (
    <aside className="flex h-full w-full flex-col bg-[var(--background)] text-foreground">
      {/* Header */}
      <header className="flex shrink-0 items-center gap-2 border-b border-[var(--border)] px-3 py-2">
        <Bot className="h-3.5 w-3.5 text-[var(--primary)]" />
        <span className="text-sm font-semibold">Syllabus Agent</span>
        <PhaseBadge phase={phase} streaming={isStreaming} />
        <div className="ml-auto flex items-center gap-1 text-[10px] text-[var(--muted-foreground)]">
          {threadId ? (
            <span className="rounded bg-[var(--muted)] px-1.5 py-0.5 font-mono">
              {threadId.slice(0, 8)}
            </span>
          ) : (
            <span className="italic">no thread</span>
          )}
          {isStreaming ? (
            <button
              type="button"
              onClick={onStop}
              className="inline-flex items-center gap-1 rounded-md border border-[var(--border)] px-2 py-0.5 text-[11px] text-[var(--muted-foreground)] transition hover:text-[var(--destructive)]"
              title="Stop the current run"
            >
              <Square className="h-3 w-3" /> Stop
            </button>
          ) : null}
        </div>
      </header>

      {/* Transcript + plans */}
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="flex-1 overflow-y-auto px-3 py-3"
      >
        {emptyState ? (
          <div className="mx-auto mt-8 max-w-sm text-center text-[13px] text-[var(--muted-foreground)]">
            <div className="mb-3 flex justify-center">
              <div className="rounded-full border border-[var(--border)] bg-[var(--card)] p-3">
                <Sparkles className="h-5 w-5 text-[var(--primary)]" />
              </div>
            </div>
            <p className="mb-2 font-semibold text-foreground">
              Start a new syllabus
            </p>
            <p>
              Ask the agent something like{" "}
              <span className="italic">
                &ldquo;Build me a syllabus about HTML for absolute beginners,
                2 chapters, 4 lessons total + a quiz per chapter.&rdquo;
              </span>
            </p>
          </div>
        ) : null}

        {/*
          Plans are rendered INLINE in the chat timeline, anchored to the
          assistant message that first called set_search_plan / set_todo_plan.
          The live `searchPlan` / `todoPlan` from state always reflects the
          most recent status, so the card keeps updating as steps advance.
        */}
        {(() => {
          // Find the first assistant message that called set_search_plan / set_todo_plan.
          let searchAnchor: string | null = null;
          let todoAnchor: string | null = null;
          for (const m of messages) {
            if (m.role !== "assistant") continue;
            if (
              !searchAnchor &&
              m.toolCalls.some((tc) => tc.name === "set_search_plan")
            ) {
              searchAnchor = m.id;
            }
            if (
              !todoAnchor &&
              m.toolCalls.some((tc) => tc.name === "set_todo_plan")
            ) {
              todoAnchor = m.id;
            }
            if (searchAnchor && todoAnchor) break;
          }

          // Fallbacks: if the plan exists in state but no anchor was found yet
          // (e.g., stream replay), append at the end so we still show it.
          let searchShown = !searchPlan || !Array.isArray(searchPlan.steps);
          let todoShown = !todoPlan || !Array.isArray(todoPlan.steps);

          const out: React.ReactNode[] = [];
          for (const m of messages) {
            out.push(<MessageBubble key={`msg-${m.id}`} m={m} />);
            if (
              !searchShown &&
              searchAnchor === m.id &&
              searchPlan &&
              Array.isArray(searchPlan.steps)
            ) {
              out.push(
                <SearchPlanCard key={`sp-${m.id}`} plan={searchPlan} />,
              );
              searchShown = true;
            }
            if (
              !todoShown &&
              todoAnchor === m.id &&
              todoPlan &&
              Array.isArray(todoPlan.steps)
            ) {
              out.push(<TodoPlanCard key={`tp-${m.id}`} plan={todoPlan} />);
              todoShown = true;
            }
          }
          if (!searchShown && searchPlan && Array.isArray(searchPlan.steps)) {
            out.push(<SearchPlanCard key="sp-tail" plan={searchPlan} />);
          }
          if (!todoShown && todoPlan && Array.isArray(todoPlan.steps)) {
            out.push(<TodoPlanCard key="tp-tail" plan={todoPlan} />);
          }
          return out;
        })()}

        {hasInterrupt ? (
          <InterruptCard
            question={interruptValue.question}
            onSubmit={answerInterrupt}
            busy={!!isStreaming}
          />
        ) : null}

        {errorText ? (
          <div className="mb-3 flex items-start gap-2 rounded-md border border-[var(--destructive)]/40 bg-[var(--destructive)]/10 p-2 text-[13px] text-[var(--destructive)]">
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <div className="break-all">{errorText}</div>
          </div>
        ) : null}

        <div ref={endRef} />
      </div>

      {/* Composer */}
      <div className="shrink-0 border-t border-[var(--border)] bg-[var(--card)]/60 p-2">
        <div className="flex items-end gap-2">
          <textarea
            value={composerText}
            onChange={(e) => setComposerText(e.target.value)}
            onKeyDown={onSendKey}
            disabled={hasInterrupt}
            rows={2}
            placeholder={
              hasInterrupt
                ? "Answer the agent's question above first."
                : "Message the syllabus agent… (Enter to send, Shift+Enter for newline)"
            }
            className="flex-1 resize-none rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-[14px] outline-none placeholder:text-[var(--muted-foreground)] focus:border-[var(--primary)] disabled:opacity-60"
          />
          <button
            type="button"
            onClick={onSendClick}
            disabled={
              !composerText.trim() || isStreaming || hasInterrupt
            }
            className="inline-flex h-9 items-center gap-1 rounded-md bg-[var(--primary)] px-3 text-[13px] font-semibold text-[var(--primary-foreground)] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isStreaming ? (
              <Pause className="h-3.5 w-3.5" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
            Send
          </button>
        </div>
        <div className="mt-1 flex items-center gap-1 text-[10px] text-[var(--muted-foreground)]">
          <Pencil className="h-2.5 w-2.5" />
          <span>
            {hasInterrupt
              ? "The agent is waiting for your answer above."
              : phase === "idle" || !phase
                ? "Idle."
                : `Phase: ${phase}`}
          </span>
          <span className="ml-auto">
            {messages.length} msg{messages.length === 1 ? "" : "s"}
          </span>
        </div>
      </div>
    </aside>
  );
}

export default ChatPane;

// ─── Unused imports referenced by legacy code, kept for completeness ─────
// We intentionally reference CheckCircle2 in type space so removing it later
// is explicit rather than tree-shaken silently.
type _Kept = typeof CheckCircle2;
