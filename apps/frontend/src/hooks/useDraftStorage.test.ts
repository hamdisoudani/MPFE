import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDraftStorage } from "./useDraftStorage";

describe("useDraftStorage", () => {
  beforeEach(() => window.localStorage.clear());

  it("persists and restores draft per threadId", () => {
    const { result } = renderHook(() => useDraftStorage("thread-a"));
    act(() => result.current.setDraft("hello"));
    expect(window.localStorage.getItem("mpfe:draft:thread-a")).toBe("hello");

    const { result: again } = renderHook(() => useDraftStorage("thread-a"));
    expect(again.current.draft).toBe("hello");
  });

  it("scopes drafts per thread", () => {
    const { result: a } = renderHook(() => useDraftStorage("t1"));
    act(() => a.current.setDraft("alpha"));
    const { result: b } = renderHook(() => useDraftStorage("t2"));
    expect(b.current.draft).toBe("");
  });

  it("clears on clearDraft", () => {
    const { result } = renderHook(() => useDraftStorage("t"));
    act(() => result.current.setDraft("x"));
    act(() => result.current.clearDraft());
    expect(result.current.draft).toBe("");
    expect(window.localStorage.getItem("mpfe:draft:t")).toBeNull();
  });
});
