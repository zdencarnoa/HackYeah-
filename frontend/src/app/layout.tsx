import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Security Copilot",
  description: "Phishing detection and incident response for organizations without a security team. Demo with simulated data.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full">{children}</body>
    </html>
  );
}
