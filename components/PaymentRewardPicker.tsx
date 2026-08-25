"use client";

import { Check, ChevronDown, CircleHelp, CreditCard } from "lucide-react";
import { useState } from "react";
import { formatMoney } from "@/lib/catalog";
import { rankPaymentRewards, type RankedPaymentReward } from "@/lib/paymentRewards";

export function PaymentRewardPicker({ amountPaise, selectedId, methodFilter, onSelect }: {
  amountPaise: number;
  selectedId: string | null;
  methodFilter: "any" | "upi" | "card" | "netbanking" | "wallet";
  onSelect: (reward: RankedPaymentReward) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const allRewards = rankPaymentRewards(amountPaise);
  const rewards = methodFilter === "any"
    ? allRewards
    : allRewards.filter((reward) => reward.type === methodFilter);
  const visibleRewards = expanded ? rewards : rewards.slice(0, 3);
  return <section className="reward-picker">
    <div className="reward-picker-heading"><CreditCard size={16} /><p><b>Rewards on cards &amp; payment apps</b><small>{rewards.length} comparison options for this payment choice</small></p></div>
    {rewards.length ? <div className="reward-list">{visibleRewards.map((reward, index) => <button type="button" className={selectedId === reward.id ? "selected" : ""} onClick={() => onSelect(reward)} key={reward.id}><span className="reward-rank">#{index + 1}</span><p><b>{reward.method}</b><small>{reward.note}</small></p><em>Up to {formatMoney(reward.estimatedRewardPaise)}</em>{selectedId === reward.id && <Check size={14} />}</button>)}</div> : <p className="reward-empty">No comparison rewards are listed for this method. You can still select it in Razorpay.</p>}
    {rewards.length > 3 && <button type="button" className="reward-toggle" onClick={() => setExpanded((value) => !value)}>{expanded ? "Show fewer rewards" : `View all ${rewards.length} rewards`}<ChevronDown size={13} className={expanded ? "expanded" : ""} /></button>}
    <small className="reward-disclaimer"><CircleHelp size={12} /> Estimates do not reduce the cart total. The buyer must own the method, and the issuer/Razorpay must confirm current eligibility.</small>
  </section>;
}
