"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { formatMoney } from "@/lib/catalog";
import { journeyApi, JourneyError } from "@/lib/journey";

type Basket = { cart_id: string; source: string; total_paise: number; order_id: string | null;
  items: Array<{ name: string; quantity: number }> };

export function SavedJourneyBaskets() {
  const [baskets, setBaskets] = useState<Basket[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void journeyApi<{ items: Basket[] }>("/api/journey/carts")
      .then(result => { if (active) setBaskets(result.items); })
      .catch(e => { if (active && !(e instanceof JourneyError && e.status === 401)) setError("Saved baskets could not load. Open My journey to retry."); });
    return () => { active = false; };
  }, []);
  if (error) return <p role="alert">{error} <Link href="/journey">My journey</Link></p>;
  if (!baskets.length) return null;
  return <section className="saved-journey-baskets" aria-label="Saved mission and watch baskets">
    <h3>Your prepared baskets</h3><p>Saved from missions and watches. Each keeps its own budget and exact approval.</p>
    {baskets.map(basket => <article key={basket.cart_id}>
      <small>{basket.source.replaceAll("_", " ")}{basket.order_id ? " · payment needs review" : " · ready to review"}</small>
      {basket.items.map((item, index) => <p key={index}>{item.name} × {item.quantity}</p>)}
      <strong>{formatMoney(basket.total_paise)}</strong>
      <Link href={`/journey?cart=${encodeURIComponent(basket.cart_id)}`}>Continue this basket →</Link>
    </article>)}
  </section>;
}
