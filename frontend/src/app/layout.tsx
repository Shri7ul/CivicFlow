import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "maplibre-gl/dist/maplibre-gl.css";

import { Providers } from "@/app/providers";
import { siteConfig } from "@/config/app";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: siteConfig.title,
    template: `%s · ${siteConfig.name}`,
  },
  description: siteConfig.description,
  applicationName: siteConfig.name,
  keywords: [
    "CivicFlow",
    "civic technology",
    "urban resilience",
    "incident response",
  ],
};

export const viewport: Viewport = {
  themeColor: "#05080b",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full antialiased">
        <a href="#main-content" className="skip-link">
          Skip to content
        </a>
        <div id="main-content" tabIndex={-1}>
          <Providers>{children}</Providers>
        </div>
      </body>
    </html>
  );
}
