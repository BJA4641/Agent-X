"use client";
import { useState } from "react";
import { supabaseBrowser } from "@/lib/supabase/client";
import Header from "@/components/Header";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");
  const configured = !!process.env.NEXT_PUBLIC_SUPABASE_URL;

  async function go(mode: "in" | "up") {
    if (!configured) { setMsg("Auth isn't configured yet — add Supabase keys (see DEPLOY.md §2)."); return; }
    const sb = supabaseBrowser();
    const { error } = mode === "in"
      ? await sb.auth.signInWithPassword({ email, password })
      : await sb.auth.signUp({ email, password });
    if (error) setMsg(error.message);
    else window.location.href = "/dashboard";
  }

  return (
    <>
      <Header />
      <div className="center"><div className="authcard card">
        <h2 style={{ marginBottom: 4 }}>Sign in</h2>
        <p className="note" style={{ marginBottom: 16 }}>Same form creates an account if you're new.</p>
        <div style={{ display: "grid", gap: 10 }}>
          <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} aria-label="Email" />
          <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} aria-label="Password" />
          <button className="primary" onClick={() => go("in")}>Sign in</button>
          <button className="ghost" onClick={() => go("up")}>Create account</button>
          {msg && <p className="note">{msg}</p>}
        </div>
      </div></div>
    </>
  );
}
