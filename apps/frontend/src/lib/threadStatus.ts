export type ThreadStatus = "idle" | "busy" | "interrupted" | "error";

export function readThreadStatus(t: any): ThreadStatus {
  const raw = (t?.status ?? t?.state ?? "idle").toString().toLowerCase();
  if (raw === "busy" || raw === "running") return "busy";
  if (raw === "interrupted" || raw === "waiting" || raw === "awaiting_input") return "interrupted";
  if (raw === "error" || raw === "failed") return "error";
  return "idle";
}

export function threadTitle(t: any): string {
  return (
    t?.values?.syllabus_title ||
    t?.values?.title ||
    t?.values?.requirements?.slice?.(0, 60) ||
    t?.metadata?.title ||
    t?.metadata?.requirements?.slice?.(0, 60) ||
    (t?.thread_id ? `Thread ${t.thread_id.slice(0, 8)}` : "Untitled")
  );
}
