"use client";
import { useState } from "react";
import type { Course } from "@/lib/courses";

type Progress = Record<string, { done: boolean; proof?: any }>;

export default function CourseView({ course, initial, locked }: { course: Course; initial: Progress; locked?: boolean }) {
  const [prog, setProg] = useState<Progress>(initial);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [open, setOpen] = useState<string | null>(null);

  const allSteps = course.modules.flatMap((m) => m.steps);
  const doneCount = allSteps.filter((s) => prog[s.key]?.done).length;
  const firstOpenIdx = allSteps.findIndex((s) => !prog[s.key]?.done);

  async function submit(stepKey: string, type: string) {
    setErr(null); setBusy(stepKey);
    let value = (vals[stepKey] || "").trim();
    try {
      if (type === "screenshot") {
        const input = document.getElementById(`file-${stepKey}`) as HTMLInputElement;
        const file = input?.files?.[0];
        if (!file) throw new Error("Attach the screenshot first.");
        const fd = new FormData(); fd.append("file", file); fd.append("stepKey", stepKey);
        const up = await fetch("/api/proof", { method: "POST", body: fd });
        const uj = await up.json();
        if (!uj.ok) throw new Error(uj.error || "Upload failed.");
        value = uj.path;
      }
      const r = await fetch("/api/progress", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ taskKey: stepKey, done: true, courseId: course.id, proof: { type, value } }) });
      const j = await r.json();
      if (!j.ok) throw new Error(j.error || "Could not save.");
      setProg({ ...prog, [stepKey]: { done: true, proof: { type, value } } });
      setOpen(null);
    } catch (e: any) { setErr(e.message); }
    setBusy(null);
  }

  let globalIdx = -1;
  return (
    <div>
      <div className="card" style={{ marginBottom: 20, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span><p className="eyebrow">Progress</p><b className="mono">{doneCount} / {allSteps.length} steps verified</b></span>
        <span className="mono" style={{ color: "var(--approved)" }}>{Math.round((doneCount / allSteps.length) * 100)}%</span>
      </div>
      {locked && (
        <div className="honest" style={{ marginBottom: 20 }}>
          <b>Preview mode.</b> You can read Module 0 free. The full track unlocks with purchase — and purchases open once our own case-study page has real numbers. Join the waitlist and you will be first.
        </div>
      )}
      {err && <div className="honest" style={{ marginBottom: 16, borderColor: "var(--draft)" }}>{err}</div>}
      {course.modules.map((mod, mi) => (
        <div key={mod.id} style={{ marginBottom: 28 }}>
          <h3 style={{ marginBottom: 4 }}>{mod.title}</h3>
          <p className="note" style={{ marginBottom: 12 }}>{mod.goal}</p>
          <div className="steps">
            {mod.steps.map((s) => {
              globalIdx += 1;
              const done = !!prog[s.key]?.done;
              const isNext = globalIdx === firstOpenIdx;
              const gated = !done && !isNext;
              const paywalled = locked && mi > 0;
              const expanded = open === s.key || (isNext && open === null && !paywalled);
              return (
                <div className="step" key={s.key} style={{ display: "block", opacity: gated || paywalled ? 0.45 : 1 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", cursor: paywalled ? "not-allowed" : "pointer" }}
                       onClick={() => !paywalled && setOpen(expanded ? "" : s.key)}>
                    <h4>{done ? "✓ " : gated ? "🔒 " : "○ "}{s.title}</h4>
                    <span className="note mono">{s.minutes} min</span>
                  </div>
                  {expanded && !paywalled && (
                    <div style={{ marginTop: 12 }}>
                      <ul style={{ display: "grid", gap: 8, paddingLeft: 18 }}>
                        {s.lesson.map((p, i) => <li key={i} style={{ lineHeight: 1.6 }}>{p}</li>)}
                      </ul>
                      {(s as any).resources?.map((r: any, i: number) => (
                        <details key={i} style={{ marginTop: 10, border: "1px solid var(--line)", borderRadius: 8, padding: "8px 12px" }}>
                          <summary style={{ cursor: "pointer", fontSize: 14, color: "var(--scheduled)" }}>{r.title}</summary>
                          <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: 13.5, lineHeight: 1.6, marginTop: 8 }}>{r.body}</pre>
                          <button className="ghost" style={{ fontSize: 12 }} onClick={() => navigator.clipboard.writeText(r.body)}>Copy</button>
                        </details>
                      ))}
                      <div style={{ marginTop: 14, borderTop: "1px solid var(--line)", paddingTop: 12 }}>
                        <p className="eyebrow">Verification — required to unlock the next step</p>
                        <p className="note" style={{ marginBottom: 8 }}>{s.verify.prompt}</p>
                        {done ? (
                          <p style={{ color: "var(--approved)" }}>✓ Verified{prog[s.key]?.proof?.type === "link" ? " — " : ""}
                            {prog[s.key]?.proof?.type === "link" && <a href={prog[s.key].proof.value} target="_blank" style={{ color: "var(--scheduled)" }}>your submission</a>}
                          </p>
                        ) : gated ? (
                          <p className="note">Complete the previous step first.</p>
                        ) : (
                          <div style={{ display: "grid", gap: 8 }}>
                            {s.verify.type === "screenshot" ? (
                              <input id={`file-${s.key}`} type="file" accept="image/*" />
                            ) : s.verify.type === "text" ? (
                              <textarea rows={3} value={vals[s.key] || ""} onChange={(e) => setVals({ ...vals, [s.key]: e.target.value })}
                                        style={{ background: "var(--bg)", color: "var(--ink)", border: "1px solid var(--line)", borderRadius: 8, padding: 10 }} />
                            ) : (
                              <input type="url" placeholder="https://…" value={vals[s.key] || ""} onChange={(e) => setVals({ ...vals, [s.key]: e.target.value })}
                                     style={{ background: "var(--bg)", color: "var(--ink)", border: "1px solid var(--line)", borderRadius: 8, padding: 10 }} />
                            )}
                            <button className="primary" disabled={busy === s.key} onClick={() => submit(s.key, s.verify.type)}>
                              {busy === s.key ? "Verifying…" : "Submit & unlock next step"}
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
