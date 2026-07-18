import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const body = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "600", "700"], variable: "--font-body" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "600"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "BuildAlong — a production line for your content page",
  description: "The studio that plans, drafts, and queues short-form video. You approve; it ships.",
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
