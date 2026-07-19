// web/lib/theme-fix.js — injected into globals to fix the "black text on black background" bug.
// v5.3 FIX: chat bubbles from non-user roles were using var(--card,#1a1a1a) which resolves
// to near-black (#1a1a1a) on top of --bg (#0f172a / dark navy) while default text is white/light.
// The #1a1a1a was invisible against the dark bg on some browsers. We globally nudge any
// .card/.chat-bubble that has a too-dark background to use --line instead.
//
// This file is safe to include from layout.tsx — it only runs client-side.
"use client";
if (typeof document !== "undefined") {
  const fix = () => {
    document.querySelectorAll<HTMLElement>('[style*="background"]').forEach(el => {
      const bg = el.style.background || el.style.backgroundColor;
      // Fix: if background is the near-black fallback, swap to lighter card color
      if (bg && (bg.includes("#1a1a1a") || bg.includes("rgb(26,26,26)"))) {
        el.style.background = "rgba(255,255,255,0.05)";
        el.style.color = "inherit";
      }
    });
  };
  // Run once DOM ready and re-run on mutations for live updates (React re-renders)
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", fix);
  } else {
    fix();
  }
  try {
    const mo = new MutationObserver(fix);
    mo.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["style","class"] });
  } catch {}
}
export {};
