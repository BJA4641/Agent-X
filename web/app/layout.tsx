import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import "../lib/theme-fix"; // v5.3: fixes black-on-black chat bubbles

const body = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "600", "700"], variable: "--font-body" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "600"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "Agent-X — AI agents that build you real income streams",
  description: "Autonomous AI agents create Reels, Shorts, TikToks, and rebranded ecommerce stores. You approve everything — nothing ships until you say so. Step-by-step paths to affiliate, YouTube ad revenue, and your own brand.",
};

// v5.3: inline theme + black-bubble fix runs BEFORE first paint so you never see invisible text.
const BOOT_JS = `
(function(){
  try{var t=localStorage.getItem("theme");if(t)document.documentElement.dataset.theme=t;}catch(e){}
  // Black-bubble fix: swap any computed #1a1a1a / rgb(26,26,26) backgrounds to a soft translucent white
  function fixBubbles(){
    if(!document.body) return;
    try{
      document.querySelectorAll('[style*="background"]').forEach(function(el){
        var bg = (el.style.background||"") + ";" + (el.style.backgroundColor||"");
        if(bg && (bg.indexOf("#1a1a1a")!==-1 || bg.indexOf("rgb(26,26,26)")!==-1 || bg.indexOf("rgb(25,25,25)")!==-1)){
          el.style.background = "rgba(255,255,255,0.06)";
          el.style.color = "inherit";
        }
      });
    }catch(e){}
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",fixBubbles);
  else fixBubbles();
  try{new MutationObserver(fixBubbles).observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:["style","class"]});}catch(e){}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: BOOT_JS }} />
      </head>
      <body className={`${body.variable} ${mono.variable}`}>
        {children}
      </body>
    </html>
  );
}
