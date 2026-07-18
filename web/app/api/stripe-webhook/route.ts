import { NextResponse } from "next/server";
import { stripe } from "@/lib/stripe";
import { supabaseAdmin } from "@/lib/supabase/server";

export async function POST(req: Request) {
  const body = await req.text();
  const sig = req.headers.get("stripe-signature") || "";
  let event: any;
  try {
    event = stripe().webhooks.constructEvent(body, sig, process.env.STRIPE_WEBHOOK_SECRET || "");
  } catch (e: any) {
    return NextResponse.json({ error: `Webhook error: ${e.message}` }, { status: 400 });
  }
  if (event.type === "checkout.session.completed") {
    const s = event.data.object;
    const { user_id, module_id } = s.metadata || {};
    if (user_id && module_id) {
      await supabaseAdmin().from("entitlements").upsert(
        { user_id, module_id, stripe_session: s.id }, { onConflict: "user_id,module_id" });
    }
  }
  return NextResponse.json({ received: true });
}
