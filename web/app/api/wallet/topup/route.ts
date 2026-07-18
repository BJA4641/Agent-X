import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

/**
 * POST /api/wallet/topup { usd: number }
 * Demo mode: if Stripe is not configured, adds the credit directly with a
 * 'bonus' transaction (for testing). When STRIPE_SECRET_KEY is present, creates
 * a Stripe Checkout session for real payment.
 */
export async function POST(req: Request) {
  const sb = supabaseServer();
  const admin = supabaseAdmin();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });
  const { usd } = await req.json();
  const amount = Number(usd);
  if (!isFinite(amount) || amount < 1 || amount > 500) return NextResponse.json({ error: "Invalid amount" }, { status: 400 });

  const stripeKey = process.env.STRIPE_SECRET_KEY;
  if (!stripeKey) {
    // DEMO MODE: credit immediately (no real payment). Replace when Stripe is live.
    const { data: w } = await admin.from("wallets").select("balance_usd").eq("user_id", user.id).maybeSingle();
    await admin.from("wallets").upsert({
      user_id: user.id,
      balance_usd: Number(w?.balance_usd || 0) + amount,
      lifetime_topup: Number(w?.lifetime_topup || 0) + amount,
      updated_at: new Date().toISOString(),
    }, { onConflict: "user_id" });
    await admin.from("wallet_transactions").insert({
      user_id: user.id, type: "deposit", amount, note: `Demo top-up $${amount}`,
    });
    return NextResponse.json({ ok: true, demo: true });
  }

  // Stripe live mode: create a checkout session
  try {
    const Stripe = require("stripe");
    const stripe = new Stripe(stripeKey);
    const session = await stripe.checkout.sessions.create({
      payment_method_types: ["card"],
      line_items: [{
        price_data: {
          currency: "usd",
          product_data: { name: `${amount} Creator Credits` },
          unit_amount: Math.round(amount * 100),
        },
        quantity: 1,
      }],
      mode: "payment",
      success_url: `${process.env.NEXT_PUBLIC_SITE_URL}/wallet?paid=1`,
      cancel_url: `${process.env.NEXT_PUBLIC_SITE_URL}/wallet?canceled=1`,
      metadata: { user_id: user.id, amount },
    });
    return NextResponse.json({ ok: true, url: session.url });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
