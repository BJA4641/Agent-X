"use client";
import { useState } from "react";
import type { Step } from "@/lib/tracks";

export default function Steps({ steps, initialDone }: { steps: Step[]; initialDone: string[] }) {
  const [done, setDone] = useState<Set<string>>(new Set(initialDone));
  async function toggle(key: string) {
    const next = new Set(done);
    const val = !next.has(key);
    val ? next.add(key) : next.delete(key);
    setDone(next);
    await fetch("/api/progress", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ taskKey: key, done: val }) });
  }
  const pct = Math.round((done.size / steps.length) * 100);
  return (
    <>
      <div className="progressbar" aria-label={`Progress ${pct}%`}><div style={{ width: `${pct}%` }} /></div>
      <p className="note">{done.size} of {steps.length} steps done</p>
      <div className="steps">
        {steps.map((s) => (
          <label className="step" key={s.key}>
            <input type="checkbox" checked={done.has(s.key)} onChange={() => toggle(s.key)} />
            <span>
              <h4>{s.title}</h4>
              <p>{s.detail}{s.href && <> <a href={s.href} target="_blank" rel="noreferrer">Open ↗</a></>}</p>
            </span>
          </label>
        ))}
      </div>
    </>
  );
}
