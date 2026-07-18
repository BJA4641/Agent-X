import { NextResponse } from "next/server";
import { supabaseServer } from "@/lib/supabase/server";
import { courseById, courseSteps } from "@/lib/courses";

export async function POST(req: Request) {
  const { taskKey, done, proof, courseId } = await req.json();
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Please sign in." }, { status: 401 });

  // course steps require a proof and require the previous step to be verified
  const course = courseId ? courseById(courseId) : null;
  if (course) {
    const steps = courseSteps(course);
    const idx = steps.findIndex((s) => s.key === taskKey);
    if (idx === -1) return NextResponse.json({ error: "Unknown step." }, { status: 400 });
    if (!proof || !proof.value || String(proof.value).trim().length < 4)
      return NextResponse.json({ error: "This step needs its verification before you can continue." }, { status: 400 });
    if (proof.type === "link" && !/^https?:\/\/.+\..+/.test(proof.value))
      return NextResponse.json({ error: "That does not look like a valid link." }, { status: 400 });
    if (idx > 0) {
      const prevKey = steps[idx - 1].key;
      const { data: prev } = await sb.from("task_progress").select("done").eq("user_id", user.id).eq("task_key", prevKey).single();
      if (!prev?.done) return NextResponse.json({ error: "Finish the previous step first — the order is the method." }, { status: 400 });
    }
  }
  const { error } = await sb.from("task_progress").upsert(
    { user_id: user.id, task_key: taskKey, done: done ?? true, proof: proof || null, updated_at: new Date().toISOString() },
    { onConflict: "user_id,task_key" });
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  return NextResponse.json({ ok: true });
}
