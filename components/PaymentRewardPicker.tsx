"use client";

import { Check, CircleHelp, CreditCard } from "lucide-react";
import { formatMoney } from "@/lib/catalog";
import { rankPaymentRewards, type RankedPaymentReward } from "@/lib/paymentRewards";

export function PaymentRewardPicker({ amountPaise, selectedId, onSelect }: {
  amountPaise: number;
  selectedId: string | null;
  onSelect: (reward: RankedPaymentReward) => void;
}) {
  const rewards = rankPaymentRewards(amountPaise);
  return <section className="reward-picker">
    <div className="reward-picker-heading"><CreditCard size={16} /><p><b>Compare payment rewards</b><small>{rewards.length} ranked options adapted from PayPack</small></p></div>
    <div className="reward-list">{rewards.map((reward, index) => <button className={selectedId === reward.id ? "selected" : ""} onClick={() => onSelect(reward)} key={reward.id}><span className="reward-rank">#{index + 1}</span><p><b>{reward.method}</b><small>{reward.note}</small></p><em>Est. {formatMoney(reward.estimatedRewardPaise)}</em>{selectedId === reward.id && <Check size={14} />}</button>)}</div>
    <small className="reward-disclaimer"><CircleHelp size={12} /> Estimates do not reduce the cart total. The buyer must own the method, and the issuer/Razorpay must confirm current eligibility.</small>
  </section>;
}
