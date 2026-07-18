import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const body = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "600", "700"], variable: "--font-body" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "600"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "Agent-X — AI agents that build you real income streams",
  description: "Autonomous AI agents create Reels, Shorts, TikToks, and rebranded ecommerce stores. You approve everything — nothing ships until you say so. Step-by-step paths to affiliate, YouTube ad revenue, and your own brand.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${body.variable} ${mono.variable}`}>
        <script dangerouslySetInnerHTML={{ __html:
          `try{var t=localStorage.getItem("theme");if(t)document.documentElement.dataset.theme=t;}catch(e){}` }} />
        {children}
      </body>
    </html>
  );
}
