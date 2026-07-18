"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function QueueTopic({ topic, source }: { topic: string; source?: string }) {
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const router = useRouter();
  async function go() {
    setState("busy");
    const r = await fetch("/api/studio", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "queue_topic", topic, source }) });
    setState(r.ok ? "done" : "idle");
    if (r.ok) router.refresh();
  }
  if (state === "done") return <span className="tag" style={{ color: "var(--approved)" }}>queued ✓</span>;
  return <button className="btn tiny" disabled={state === "busy"} onClick={go}>{state === "busy" ? "…" : "Queue my version"}</button>;
}
