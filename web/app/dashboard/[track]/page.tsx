import { notFound } from "next/navigation";
import { trackById } from "@/lib/tracks";
import { courseById } from "@/lib/courses";
import { supabaseServer } from "@/lib/supabase/server";
import Steps from "@/components/Steps";
import CourseView from "@/components/CourseView";

export default async function TrackPage({ params }: { params: { track: string } }) {
  const track = trackById(params.track);
  if (!track) notFound();
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  const { data } = await sb.from("task_progress").select("task_key,done,proof");
  const progress: Record<string, any> = {};
  (data || []).forEach((r) => { progress[r.task_key] = { done: r.done, proof: r.proof }; });

  const course = courseById(params.track);
  let locked = false;
  if (course && track.price > 0 && user) {
    const { data: ent } = await sb.from("entitlements").select("module_id").eq("user_id", user.id).eq("module_id", track.id);
    locked = !ent || ent.length === 0;
  }
  return (
    <>
      <h2>{track.name}</h2>
      <p className="lead">{track.blurb}</p>
      {course ? (
        <CourseView course={course} initial={progress} locked={locked} />
      ) : (
        <Steps steps={track.steps} initialDone={Object.keys(progress).filter((k) => progress[k].done)} />
      )}
    </>
  );
}
