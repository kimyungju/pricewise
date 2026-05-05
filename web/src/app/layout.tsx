import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://pricewise-ai-shop.vercel.app"),
  title: {
    default: "Pricewise — AI Shopping Agent",
    template: "%s | Pricewise",
  },
  description:
    "AI-powered product search and price comparison with selective human-in-the-loop approval. Built with LangGraph, OpenAI, and FastAPI.",
  openGraph: {
    title: "Pricewise — AI Shopping Agent",
    description:
      "AI-powered product search and price comparison with selective human-in-the-loop approval.",
    url: "https://pricewise-ai-shop.vercel.app",
    siteName: "Pricewise",
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Pricewise — AI Shopping Agent",
    description:
      "AI-powered product search and price comparison with selective human-in-the-loop approval.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem("pricewise_theme");if(t)document.documentElement.setAttribute("data-theme",t);else if(window.matchMedia("(prefers-color-scheme:dark)").matches)document.documentElement.setAttribute("data-theme","dark")}catch(e){}})()`,
          }}
        />
      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
