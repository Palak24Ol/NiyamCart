import Link from "next/link";
import { Check, ShieldCheck } from "lucide-react";
import { formatMoney } from "@/lib/catalog";

type ReviewedCart = {
  id: string;
  cart_hash: string;
  total_paise: number;
  expires_at: string;
  items: Array<{
    product_id: string;
    product_name: string;
    quantity: number;
    unit_price_paise: number;
    line_total_paise: number;
  }>;
};

export default async function ReviewPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const response = await fetch(
    `${apiBase}/api/notifications/whatsapp/review/${encodeURIComponent(token)}`,
    { cache: "no-store" },
  );
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    return (
      <main className="review-page">
        <section className="review-card">
          <ShieldCheck size={30} />
          <h1>This review link is unavailable</h1>
          <p>{payload.message || "It may be invalid, expired, or no longer match the cart."}</p>
          <Link href="/">Return to NiyamCart</Link>
        </section>
      </main>
    );
  }
  const cart = payload.cart as ReviewedCart;
  return (
    <main className="review-page">
      <section className="review-card">
        <span className="review-badge"><Check size={14} /> Signed review-only link</span>
        <h1>Review this exact cart</h1>
        <p>This page cannot approve, order, or pay. Continue in NiyamCart to take any financial action.</p>
        <div className="review-lines">
          {cart.items.map((item) => (
            <div key={item.product_id}>
              <span><b>{item.product_name}</b><small>{item.product_id} · Qty {item.quantity}</small></span>
              <strong>{formatMoney(item.line_total_paise)}</strong>
            </div>
          ))}
        </div>
        <div className="review-total"><span>Exact total</span><b>{formatMoney(cart.total_paise)}</b></div>
        <code title={cart.cart_hash}>{cart.cart_hash}</code>
        <small>Link expires {new Date(cart.expires_at.endsWith("Z") ? cart.expires_at : `${cart.expires_at}Z`).toLocaleString("en-IN")}</small>
        <Link href="/">Open NiyamCart to continue</Link>
      </section>
    </main>
  );
}
