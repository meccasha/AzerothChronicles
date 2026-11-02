import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { Providers } from "./providers";

// Self-hosted (OFL) so builds need no network access to Google Fonts.
const cinzel = localFont({ src: "./fonts/Cinzel-latin.woff2", weight: "400 900", variable: "--font-cinzel", display: "swap" });
const inter = localFont({ src: "./fonts/Inter-latin.woff2", weight: "100 900", variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Azeroth Chronicles", template: "%s · Azeroth Chronicles" },
  description: "A private adventure journal for your World of Warcraft group.",
};

export const viewport: Viewport = { themeColor: "#0a0e16", colorScheme: "dark" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${cinzel.variable} ${inter.variable}`}>
      <body className="min-h-dvh font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
