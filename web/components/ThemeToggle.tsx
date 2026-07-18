"use client";
import { useEffect, useState } from "react";

export default function ThemeToggle() {
  const [theme, setTheme] = useState<string>("dark");
  useEffect(() => { setTheme(document.documentElement.dataset.theme || "dark"); }, []);
  const flip = () => {
    const next = theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch {}
    setTheme(next);
  };
  return (
    <button onClick={flip} className="ghost" title="Toggle light / dark"
            style={{ fontSize: 14, padding: "4px 10px", marginLeft: 16 }}>
      {theme === "light" ? "☾ dark" : "☀ light"}
    </button>
  );
}
