import type { Metadata } from "next";
import "@xyflow/react/dist/style.css";

import { AppShell } from "@/components/layout/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dr. Robot | Lifetime & Family Health Intelligence",
  description:
    "A privacy-first prototype for organizing and understanding longitudinal health information.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body><AppShell>{children}</AppShell></body>
    </html>
  );
}
