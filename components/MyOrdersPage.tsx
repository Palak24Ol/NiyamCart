"use client";

import { ArrowRight, Check, Clock3, Package, ReceiptText, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { formatMoney } from "@/lib/catalog";
import { loadSavedOrders, type SavedOrder } from "@/lib/customer";
import { getCurrentUser } from "@/lib/auth";

const serverTimestamp = (value: string) =>
  new Date(/[zZ]$|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);

export function MyOrdersPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<SavedOrder[] | null>(null);
  useEffect(() => {
    void getCurrentUser()
      .then(() => setOrders(loadSavedOrders()))
      .catch(() => router.replace("/auth?next=/orders"));
  }, [router]);

  return (
    <>
      <section className="account-hero">
        <div><span className="kicker">YOUR PURCHASES</span><h1>My orders</h1><p>Verified test purchases from this browser, with the exact products and payment evidence kept easy to review.</p></div>
        <div className="account-hero-badge"><ShieldCheck size={20} /><span><b>Buyer approved</b><small>Every paid order passed exact-cart approval</small></span></div>
      </section>

      {orders === null && <div className="orders-loading"><Clock3 size={20} /> Loading your orders…</div>}
      {orders?.length === 0 && (
        <section className="orders-empty">
          <span><Package size={32} /></span><h2>No orders in this browser yet</h2>
          <p>Complete a Razorpay test checkout while signed in and the verified receipt will appear here automatically.</p>
          <Link className="primary-button" href="/">Explore products <ArrowRight size={17} /></Link>
        </section>
      )}
      {!!orders?.length && <div className="orders-list">{orders.map((order) => (
        <article className="order-card" key={order.orderId}>
          <header>
            <div><span className="order-status"><Check size={13} /> Payment verified</span><h2>Order {order.orderId.slice(0, 8).toUpperCase()}</h2><p>{serverTimestamp(order.verifiedAt).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</p></div>
            <strong>{formatMoney(order.amountPaise)}</strong>
          </header>
          <div className="order-items">{order.items.map((item) => (
            <div className="order-item" key={item.productId}>
              <img src={item.image} alt="" /><span><b>{item.name}</b><small>Qty {item.quantity} · {formatMoney(item.unitPricePaise)} each</small></span><strong>{formatMoney(item.unitPricePaise * item.quantity)}</strong>
            </div>
          ))}</div>
          <dl className="order-evidence">
            <div><dt>Order ID</dt><dd title={order.orderId}>{order.orderId}</dd></div>
            <div><dt>Razorpay test payment</dt><dd title={order.paymentId}>{order.paymentId}</dd></div>
            <div><dt>WhatsApp</dt><dd>{order.whatsappStatus}</dd></div>
            <div><dt>Cart hash</dt><dd title={order.cartHash}>{order.cartHash}</dd></div>
          </dl>
          <footer><span><ReceiptText size={15} /> TEST MODE · No real money charged</span><Link href="/">Shop again <ArrowRight size={14} /></Link></footer>
        </article>
      ))}</div>}
    </>
  );
}
