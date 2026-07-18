"use client";
import { useState } from "react";
export default function Waitlist() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  async function join() {
    if (!email.includes("@")) return;
    setState("busy");
    const r = await fetch("/api/waitlist", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) });
    setState(r.ok ? "done" : "error");
  }
  if (state === "done") return <p className="note" style={{ color: "var(--approved)", fontSize: 15 }}>You're on the list. First look goes to the waitlist when the case study ships.</p>;
  return (
    <form className="inline" onSubmit={(e) => { e.preventDefault(); join(); }}>
      <input type="email" required placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} aria-label="Email address" />
      <button className="primary" type="submit" disabled={state === "busy"}>{state === "busy" ? "Adding…" : "Join the waitlist"}</button>
      {state === "error" && <p className="note">Couldn't save that — check the address and try again.</p>}
    </form>
  );
}
