import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "aigent",
  description: "AI-powered product search with human-in-the-loop approval",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
