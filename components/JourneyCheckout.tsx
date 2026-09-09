"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Check, LockKeyhole, X } from "lucide-react";
import { formatMoney } from "@/lib/catalog";
import { dateLabel, journeyApi, type Quote } from "@/lib/journey";
import { approveAndOpenCheckout, confirmDelivery, finalizeCheckoutCart, getAddresses,
  getPaymentOffers, openExistingOrderCheckout, saveAddress, selectPaymentOffer, type ApprovalCart, type DeliveryAddress,
  type PaymentOffer } from "@/lib/checkout";

type Review = {
  cart: ApprovalCart & { status: string; subtotal_paise: number;
    items: Array<{ product_id: string; product_name: string; quantity: number; line_total_paise: number }> };
  address_id: string | null; order_id: string | null; quote: Quote;
};
const emptyAddress = { label: "Home", recipient_name: "", phone: "", line1: "", locality: "",
  landmark: "", city: "", state: "", pincode: "", latitude: null, longitude: null, is_default: false };

export function JourneyCheckout({ cartId, close }: { cartId: string; close: () => void }) {
  const [review, setReview] = useState<Review | null>(null);
  const [addresses, setAddresses] = useState<DeliveryAddress[]>([]);
  const [addressId, setAddressId] = useState("");
  const [address, setAddress] = useState(emptyAddress);
  const [addingAddress, setAddingAddress] = useState(false);
  const [offers, setOffers] = useState<PaymentOffer[]>([]);
  const [offer, setOffer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [paid, setPaid] = useState(false);

  const refresh = useCallback(async () => {
    setReview(await journeyApi<Review>(`/api/journey/carts/${cartId}`));
  }, [cartId]);
  useEffect(() => {
    void Promise.all([journeyApi<Review>(`/api/journey/carts/${cartId}`), getAddresses(), getPaymentOffers(cartId)])
      .then(([next, saved, available]) => {
        setReview(next); setAddresses(saved); setAddressId(next.address_id || saved[0]?.id || "");
        setOffers(available.items); setOffer(available.items.find(o => o.key === available.best_offer_key && o.eligible)?.key ||
          available.items.find(o => o.eligible && o.status !== "preview")?.key || "");
      }).catch(e => setError(e.message));
  }, [cartId]);

  async function act(work: () => Promise<void>) {
    setBusy(true); setError(""); setMessage("");
    try { await work(); }
    catch (e) { setError(e instanceof Error ? e.message : "Checkout could not be completed."); }
    finally { await refresh().catch(() => undefined); setBusy(false); }
  }

  const canLock = review?.cart.status === "proposed";
  return <section className="journey-panel journey-checkout" aria-label="Review prepared basket">
    <div className="journey-heading"><h2><LockKeyhole size={20} />Review your prepared basket</h2>
      <button onClick={close} aria-label="Close basket review"><X size={18} /></button></div>
    {error && <p className="journey-alert" role="alert">{error}</p>}
    {message && <p className="journey-success" role="status">{message}</p>}
    {!review && !error && <p role="status">Loading your basket…</p>}
    {review && <>
      {review.cart.items.map(item => <div className="journey-heading" key={item.product_id}><span>{item.product_name} × {item.quantity}</span><b>{formatMoney(item.line_total_paise)}</b></div>)}
      <div className="journey-heading"><span>Delivery estimate</span><b>{formatMoney(review.quote.shipping_paise)}</b></div>
      <div className="journey-heading journey-total"><strong>{canLock ? "Estimated total" : "Locked total"}</strong><strong>{formatMoney(canLock ? review.quote.total_paise : review.cart.total_paise)}</strong></div>
      <small>Catalogue delivery estimate: {dateLabel(review.quote.estimated_arrival)}. Final total is rechecked before approval.</small>
      {canLock && <>
        <label>Delivery address<select value={addressId} onChange={e => setAddressId(e.target.value)}>
          <option value="">Choose an address</option>{addresses.map(a => <option value={a.id} key={a.id}>{a.label} · {a.line1}, {a.city} {a.pincode}</option>)}</select></label>
        <button onClick={() => setAddingAddress(!addingAddress)}>{addingAddress ? "Close address form" : "Add an address"}</button>
        {addingAddress && <form onSubmit={e => { e.preventDefault(); void act(async () => {
          const saved = await saveAddress(address); setAddresses(await getAddresses()); setAddressId(saved.id); setAddingAddress(false);
        }); }}><div className="journey-fields">
          {([['recipient_name', 'Recipient'], ['phone', 'Phone'], ['line1', 'House / street'], ['locality', 'Locality'],
            ['city', 'City'], ['state', 'State'], ['pincode', 'Pincode']] as Array<[keyof typeof emptyAddress, string]>).map(([key, label]) =>
            <label key={key}>{label}<input required value={String(address[key] ?? "")} maxLength={key === "pincode" ? 6 : key === "phone" ? 16 : 80}
              pattern={key === "pincode" ? "[1-9][0-9]{5}" : undefined}
              onChange={e => setAddress({ ...address, [key]: e.target.value })} /></label>)}
        </div><button disabled={busy}>Save address</button></form>}
        <label>Payment option<select value={offer} onChange={e => setOffer(e.target.value)}>
          <option value="">Choose a payment option</option>{offers.map(o => <option key={o.key} value={o.key}
            disabled={!o.eligible || o.status === "preview"}>{o.title}{o.status === "preview" ? " (preview only)" : ""}</option>)}</select></label>
        <p className="journey-footnote">{offers.find(o => o.key === offer)?.terms}</p>
        <button className="journey-primary" disabled={busy || !addressId || !offer} onClick={() => void act(async () => {
          await confirmDelivery(cartId, addressId);
          await selectPaymentOffer(cartId, offer);
          await finalizeCheckoutCart(cartId); setMessage("Basket locked. Review the total, then approve payment separately.");
        })}>Confirm delivery & lock total</button>
      </>}
      {review.cart.status === "frozen" && !paid && <div className="journey-approval">
        <p>Locked until {dateLabel(review.cart.expires_at)}. This approval applies to these exact products and this total.</p>
        <button className="journey-primary" disabled={busy} onClick={() => void act(async () => {
          await approveAndOpenCheckout(review.cart); setPaid(true); setMessage("Payment verified. Your order is saved in your account.");
        })}>Approve {formatMoney(review.cart.total_paise)} & open test payment</button>
      </div>}
      {(review.order_id || paid) && <p className="journey-success"><Check size={17} />{paid ? "Payment verified." : "An order already exists for this basket."}
        <Link href={`/orders${review.order_id ? `?order=${review.order_id}` : ""}`}>View verified order status</Link></p>}
      {review.order_id && !paid && <button className="journey-primary" disabled={busy} onClick={() => void act(async () => {
        await openExistingOrderCheckout(review.order_id!, true);
        setPaid(true); setMessage("Payment verified. Your order is saved in your account.");
      })}>Recheck & reopen test checkout</button>}
      {!review.order_id && !paid && !["proposed", "frozen"].includes(review.cart.status) && <p>Basket status: {review.cart.status}. Check for an existing order before preparing another basket.</p>}
      {!paid && <div className="journey-actions"><button disabled={busy} onClick={() => void act(async () => {
        await journeyApi("/api/journey/tasks", { kind: "recovery", cart_id: cartId, consent: true });
        setMessage("Recovery enabled. Check Watches & reminders for the next step.");
      })}>Enable checkout recovery</button></div>}
    </>}
    <p className="journey-footnote">Razorpay test mode · Every payment needs your explicit approval.</p>
  </section>;
}
