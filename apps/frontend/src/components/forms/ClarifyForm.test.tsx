import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ClarifyForm } from "./ClarifyForm";

const interrupt = {
  kind: "clarification" as const,
  findings_summary: "We found X, Y, Z.",
  questions: [
    { key: "target_audience", kind: "text" as const, prompt: "Audience?", default: "Adult beginners" },
    { key: "num_chapters",    kind: "number" as const, prompt: "Chapters?", default: 10 },
    { key: "include_activities", kind: "boolean" as const, prompt: "Include activities?", default: true },
    { key: "pedagogical_approach", kind: "single_choice" as const, prompt: "Approach?",
      options: ["mixed", "task_based"], default: "mixed" },
    { key: "special_focus", kind: "multi_choice" as const, prompt: "Focus?",
      options: ["speaking", "writing"], default: [] },
  ],
};

describe("ClarifyForm", () => {
  it("renders findings and all question kinds", () => {
    render(<ClarifyForm interrupt={interrupt} onSubmit={() => {}} />);
    expect(screen.getByText("We found X, Y, Z.")).toBeInTheDocument();
    expect(screen.getByText("Audience?")).toBeInTheDocument();
    expect(screen.getByText("Chapters?")).toBeInTheDocument();
    expect(screen.getByText("Include activities?")).toBeInTheDocument();
    expect(screen.getByText("Approach?")).toBeInTheDocument();
    expect(screen.getByText("Focus?")).toBeInTheDocument();
  });

  it("submits defaulted values via onSubmit", async () => {
    const onSubmit = vi.fn();
    render(<ClarifyForm interrupt={interrupt} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));
    expect(onSubmit).toHaveBeenCalledWith({
      target_audience: "Adult beginners",
      num_chapters: 10,
      include_activities: true,
      pedagogical_approach: "mixed",
      special_focus: [],
    });
  });

  it("toggles multi_choice chips on click", () => {
    const onSubmit = vi.fn();
    const { container } = render(<ClarifyForm interrupt={interrupt} onSubmit={onSubmit} />);
    const chip = Array.from(container.querySelectorAll("button"))
      .find((b) => b.textContent?.trim() === "speaking");
    expect(chip).toBeDefined();
    fireEvent.click(chip!);
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));
    expect(onSubmit.mock.calls[0][0].special_focus).toEqual(["speaking"]);
  });
});
