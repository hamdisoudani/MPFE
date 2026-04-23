"use client";
import { Suspense } from "react";
import { AppShell } from "@/components/layout/AppShell";

export default function HomePage() {
  return (
    <Suspense fallback={null}>
      <AppShell />
    </Suspense>
  );
}
