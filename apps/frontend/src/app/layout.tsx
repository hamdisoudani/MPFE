import type { Metadata } from "next";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import "./globals.css";

export const metadata: Metadata = {
  title: "MPFE — AI syllabus studio",
  description: "Plan, review and publish AI-generated teaching syllabi in real time.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full">
        <NuqsAdapter>{children}</NuqsAdapter>
      </body>
    </html>
  );
}
