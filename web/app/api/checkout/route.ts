import { NextResponse } from "next/server";
import { stripe } from "@/lib/stripe";
import { supabaseServer } from "@/lib/supabase/server";

const PRICES: Record<string, string | undefined> = {
  youtube: process.env.STRIPE_PRICE_YT,
  store: process.env.STRIPE_PRICE_ECOM,
};

export async function POST(req: Request) {
  const { moduleId } = await req.json();
  const price = PRICES[moduleId];
  if (!price) return NextResponse.json({ error: "This track isn't purchasable yet." }, { status: 400 });
  const { data: { user } } = await supabaseServer().auth.getUser();
  if (!user) return NextResponse.json({ error: "Please sign in." }, { status: 401 });
  const site = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
  const session = await stripe().checkout.sessions.create({
    mode: "payment",
    line_items: [{ price, quantity: 1 }],
    success_url: `${site}/dashboard/${moduleId}?unlocked=1`,
    cancel_url: `${site}/dashboard`,
    metadata: { user_id: user.id, module_id: moduleId },
    customer_email: user.email || undefined,
  });
  return NextResponse.json({ url: session.url });
}
