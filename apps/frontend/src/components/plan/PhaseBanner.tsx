"use client";
import { cn } from "@/lib/cn";
import type { Phase } from "@/lib/types";

const LABEL: Record<Phase, string> = {
  searching: "Researching sources…",
  awaiting_input: "Waiting for your input",
  outlining: "Generating the outline",
  writing: "Drafting chapters & lessons",
  activities: "Generating activities",
  done: "Completed",
  failed: "Failed",
};

export function PhaseBanner({ phase }: { phase: Phase | null | undefined }) {
  if (!phase) return null;
  const tone =
    phase === "done" ? "chip-accent" :
    phase === "failed" ? "chip-err" :
    phase === "awaiting_input" ? "chip-warn" :
    "chip-accent";
  const animated = !["done", "failed", "awaiting_input"].includes(phase);
  return (
    <span className={cn(tone, "px-3 py-1 text-xs")}>
      {animated && <span className="dot text-accent" />}
      {LABEL[phase]}
    </span>
  );
}
