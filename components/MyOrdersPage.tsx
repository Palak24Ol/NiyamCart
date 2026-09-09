"use client";

import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowRight, Check, Clock3, Package, RefreshCw, Send, ShieldCheck } from "lucide-react";
import { formatMoney } from "@/lib/catalog";
import { openExistingOrderCheckout } from "@/lib/checkout";
import { dateLabel, getCustomerOrders, JOURNEY_API, journeyApi, JourneyError,
  type CustomerOrder, type JourneyProduct, type Dashboard } from "@/lib/journey";

export function MyOrdersPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<CustomerOrder[] | null>(null);
  const [error, setError] = useState("");
  const [demoEnabled, setDemoEnabled] = useState(false);
  const refresh = useCallback(async () => setOrders((await getCustomerOrders()).items), []);
  useEffect(() => {
    void getCustomerOrders().then(result => setOrders(result.items)).catch((e: Error) => {
      if (e instanceof JourneyError && e.status === 401) router.replace("/auth?next=/orders");
      else setError(e.message);
    });
    void journeyApi<Dashboard>("/api/journey").then(d => setDemoEnabled(d.demo_fulfillment_enabled)).catch(() => undefined);
    const timer = window.setInterval(() => { if (!document.hidden) void refresh().catch(() => undefined); }, 30_000);
    return () => window.clearInterval(timer);
  }, [refresh, router]);

  return <div className="journey">
    <section className="account-hero"><div><span className="kicker">FROM CHECKOUT TO YOUR DOOR</span><h1>My orders</h1>
      <p>Your account’s orders, delivery updates and support requests, synced across devices.</p></div>
      <div className="account-hero-badge"><ShieldCheck size={20} /><span><b>Verified records</b><small>Payment facts come from the backend</small></span></div></section>
    {error && <p className="journey-alert" role="alert">{error}<button onClick={() => void refresh().then(() => setError("")).catch(e => setError(e.message))}>Retry</button></p>}
    {orders === null && !error && <div className="orders-loading"><Clock3 size={20} />Loading your orders…</div>}
    {orders?.length === 0 && <section className="journey-empty"><Package size={32} /><h2>No account orders yet</h2>
      <p>Orders with an address confirmed by this account appear here, including pending checkouts. Old browser-only receipts remain on your device.</p>
      <div className="journey-actions"><Link href="/journey">Start a shopping mission <ArrowRight size={16} /></Link></div></section>}
    {orders?.map(order => <OrderCard key={order.orderId} order={order} refresh={refresh} demoEnabled={demoEnabled} />)}
  </div>;
}

function OrderCard({ order, refresh, demoEnabled }: { order: CustomerOrder; refresh: () => Promise<void>; demoEnabled: boolean }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [canResume, setCanResume] = useState(false);
  const [days, setDays] = useState(30);
  const [kind, setKind] = useState("support");
  const [reason, setReason] = useState("");
  const [productId, setProductId] = useState(order.items[0]?.productId || "");
  const [replacements, setReplacements] = useState<JourneyProduct[]>([]);
  const [replacementId, setReplacementId] = useState("");
  const [requestKey, setRequestKey] = useState("");
  const [demoStatus, setDemoStatus] = useState("shipped");

  async function act(work: () => Promise<unknown>, success = "") {
    setBusy(true); setError(""); setNotice("");
    try { await work(); await refresh(); setNotice(success); }
    catch (e) { setError(e instanceof Error ? e.message : "Request failed. Please try again."); }
    finally { setBusy(false); }
  }
  async function ask(message = question) {
    const result = await journeyApi<{ answer: string; mode: string }>(`/api/customer/orders/${order.orderId}/ask`, { message });
    setAnswer(result.answer); setQuestion("");
  }
  async function downloadReceipt() {
    const response = await fetch(`${JOURNEY_API}/api/customer/orders/${order.orderId}/receipt`, { credentials: "include" });
    if (!response.ok) throw new Error("A receipt is available after verified payment.");
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `niyamcart-${order.orderId.slice(0, 8)}-receipt.txt`;
    anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <article className="journey-panel" id={`order-${order.orderId}`}>
    <header className="journey-heading"><div><span className="journey-badge">{order.status === "paid" ? "Payment verified" : order.status.replaceAll("_", " ")}</span>
      <h2>Order {order.orderId.slice(0, 8).toUpperCase()}</h2><small>{dateLabel(order.verifiedAt || order.createdAt)}</small></div>
      <strong>{formatMoney(order.amountPaise)}</strong></header>
    {order.items.map(item => <div className="journey-product" key={item.productId}>{item.image && <Image src={item.image} alt="" width={48} height={58} unoptimized />}
      <span>{item.name}<small>Qty {item.quantity} · {formatMoney(item.unitPricePaise)} each</small></span>
      <b>{formatMoney(item.unitPricePaise * item.quantity)}</b></div>)}
    {error && <p className="journey-alert" role="alert">{error}</p>}
    {notice && <p className="journey-success" role="status"><Check size={16} />{notice}</p>}
    <div className="journey-order-tools">
      <div className="journey-heading"><h3>Delivery</h3><span className="journey-badge">{order.shipment_status.replaceAll("_", " ")}</span></div>
      {order.shipment_source === "demo_simulation" && <p className="journey-question">Test shipment simulation. These events are not carrier tracking.</p>}
      {order.estimated_arrival && <p>Catalogue estimate: {dateLabel(order.estimated_arrival)}{order.is_late ? " · The estimated date has passed; ask the merchant for an update." : ""}</p>}
      {!order.events.length && <p>No carrier event received yet. Payment verification does not confirm dispatch.</p>}
      <div className="journey-timeline">{order.events.map(event => <p key={event.id}><b>{event.status.replaceAll("_", " ")}</b> · {event.detail}<small>{dateLabel(event.occurred_at)}</small></p>)}</div>
      <form onSubmit={e => { e.preventDefault(); void act(() => ask()); }}>
        <label>Ask about this order<input required minLength={3} maxLength={1000} value={question}
          onChange={e => setQuestion(e.target.value)} placeholder="Where’s my order? Can I exchange it?" /></label>
        <div className="journey-actions"><button disabled={busy}><Send size={15} />Ask Niyam</button>
          <button type="button" disabled={busy} onClick={() => void act(() => ask("Where is my order?"))}>Track order</button>
          {order.status === "paid" && <button type="button" disabled={busy} onClick={() => void act(downloadReceipt)}>Download payment receipt</button>}
          {order.status !== "paid" && <button type="button" disabled={busy} onClick={() => void act(async () => {
            const result = await journeyApi<{ message: string; can_resume: boolean }>(`/api/customer/orders/${order.orderId}/reconcile`, {}); setAnswer(result.message); setCanResume(result.can_resume);
          })}><RefreshCw size={15} />Recheck payment</button>}</div>
      </form>
      {answer && <p className="journey-question" role="status">{answer}</p>}
      {canResume && order.status !== "paid" && <button className="journey-primary" disabled={busy} onClick={() => void act(async () => {
        await openExistingOrderCheckout(order.orderId, true); setCanResume(false);
      }, "Payment verified for your existing order.")}>Reopen approved {formatMoney(order.amountPaise)} test payment</button>}
    </div>
    {order.status === "paid" && <details><summary>Repeat this purchase</summary>
      <label>Remind me every (days)<input type="number" min="1" max="180" value={days} onChange={e => setDays(Number(e.target.value))} /></label>
      <p>We’ll prepare a fresh basket within the original total and ask you to review it. Changed products or prices need your attention.</p>
      <button disabled={busy} onClick={() => void act(() => journeyApi("/api/journey/tasks", {
        kind: "replenish", order_id: order.orderId, interval_days: days,
        expires_at: new Date(Date.now() + 365 * 86_400_000).toISOString(), consent: true,
      }), "Reorder reminder saved. You can pause or stop it in My journey.")}>Enable reorder reminder</button>
    </details>}
    <details><summary>Help, returns & exchanges</summary>
      <form onSubmit={e => { e.preventDefault(); void act(async () => {
        const key = requestKey || crypto.randomUUID(); setRequestKey(key);
        await journeyApi(`/api/customer/orders/${order.orderId}/cases`, { kind, message: reason,
          product_id: kind === "support" ? null : productId, replacement_product_id: kind === "exchange" ? replacementId : null,
          request_key: key }); setRequestKey(""); setReason("");
      }, "Request prepared. Review the details below before submitting."); }}>
        <div className="journey-fields"><label>Request type<select value={kind} onChange={e => { setKind(e.target.value); setRequestKey(""); }}>
          <option value="support">Get help</option><option value="return">Return an item</option><option value="exchange">Exchange an item</option></select></label>
          {kind !== "support" && <label>Item<select value={productId} onChange={e => { setProductId(e.target.value); setRequestKey(""); setReplacements([]); setReplacementId(""); }}>
            {order.items.map(item => <option key={item.productId} value={item.productId}>{item.name}{!item.return_eligible ? " (needs eligibility review)" : ""}</option>)}</select></label>}</div>
        {kind !== "support" && <p>Eligibility uses recorded delivery and the current merchant return window. The request covers the full purchased quantity of the selected item.</p>}
        {kind === "exchange" && <><button type="button" disabled={busy} onClick={() => void act(async () => {
          const result = await journeyApi<{ items: JourneyProduct[] }>(`/api/customer/orders/${order.orderId}/replacements?product_id=${encodeURIComponent(productId)}`);
          setReplacements(result.items); setReplacementId(result.items[0]?.id || "");
        })}>Find available replacements</button>
          <label>Replacement<select required value={replacementId} onChange={e => { setReplacementId(e.target.value); setRequestKey(""); }}>
            <option value="">Choose a replacement</option>{replacements.map(p => <option key={p.id} value={p.id}>{p.name} · {formatMoney(p.price_paise)}</option>)}</select></label>
          <small>Size-specific variants are not in this catalogue. Contact the merchant for a size-only exchange.</small></>}
        <label>Tell us what happened<textarea required minLength={3} maxLength={1000} rows={3} value={reason}
          onChange={e => { setReason(e.target.value); setRequestKey(""); }} /></label>
        <button disabled={busy}>Prepare request</button>
      </form>
    </details>
    {order.cases.map(item => <div className="journey-case" key={item.id}><div className="journey-heading"><b>{item.kind} request</b><span className="journey-badge">{item.status.replaceAll("_", " ")}</span></div>
      <p>{item.details.message}</p>
      {item.details.estimated_refund_paise !== undefined && <p>Item-value estimate: {formatMoney(item.details.estimated_refund_paise)}. Shipping excluded; merchant review required.</p>}
      {item.details.replacement && <p>Replacement: {item.details.replacement.name} · Price difference: {formatMoney(item.details.price_difference_paise || 0)}</p>}
      {item.details.delivery_source === "demo_simulation" && <small>Eligibility demonstrated using simulated delivery.</small>}
      {item.status === "draft" && <div className="journey-actions"><button disabled={busy} onClick={() => void act(() => journeyApi(`/api/journey/cases/${item.id}/confirm`, {}), "Request submitted to the local merchant review queue.")}>Confirm & submit request</button>
        <button disabled={busy} onClick={() => void act(() => journeyApi(`/api/journey/cases/${item.id}/cancel`, {}))}>Discard draft</button></div>}
      {item.status === "awaiting_merchant" && <small>Saved in the merchant review queue. No refund, collection or replacement has been executed.</small>}
    </div>)}
    {demoEnabled && order.status === "paid" && <details><summary>Test shipment simulator</summary>
      <p>Add a clearly labelled event to rehearse post-purchase flows. Real tracking requires the signed merchant integration.</p>
      <label>Simulated update<select value={demoStatus} onChange={e => setDemoStatus(e.target.value)}>
        {['confirmed', 'shipped', 'out_for_delivery', 'delayed', 'delivered'].map(s => <option key={s} value={s}>{s.replaceAll("_", " ")}</option>)}</select></label>
      <button disabled={busy} onClick={() => void act(() => journeyApi("/api/journey/demo/shipment", {
        event_id: crypto.randomUUID(), order_id: order.orderId, status: demoStatus,
        detail: `Demo shipment ${demoStatus.replaceAll("_", " ")}. No carrier action occurred.`, occurred_at: new Date().toISOString(),
      }))}>Add simulated event</button>
    </details>}
    <details><summary>Payment evidence</summary><p className="journey-evidence">Order: {order.orderId}<br />Payment: {order.paymentId || "Not verified"}<br />Cart: {order.cartHash}</p></details>
    <p className="journey-footnote">Razorpay test mode · No real money charged.</p>
  </article>;
}
