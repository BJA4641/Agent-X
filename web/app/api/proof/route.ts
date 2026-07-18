import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

export async function POST(req: Request) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Please sign in." }, { status: 401 });
  const form = await req.formData();
  const file = form.get("file") as File | null;
  const stepKey = String(form.get("stepKey") || "step");
  if (!file) return NextResponse.json({ error: "No file." }, { status: 400 });
  if (file.size > 8 * 1024 * 1024) return NextResponse.json({ error: "Max 8MB." }, { status: 400 });
  if (!file.type.startsWith("image/")) return NextResponse.json({ error: "Images only." }, { status: 400 });
  const ext = (file.name.split(".").pop() || "png").toLowerCase().replace(/[^a-z0-9]/g, "");
  const path = `${user.id}/${stepKey}-${Date.now()}.${ext}`;
  const buf = Buffer.from(await file.arrayBuffer());
  const { error } = await supabaseAdmin().storage.from("proofs").upload(path, buf, { contentType: file.type, upsert: true });
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  return NextResponse.json({ ok: true, path });
}
