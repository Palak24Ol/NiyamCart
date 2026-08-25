export type PaymentReward = {
  id: string;
  method: string;
  type: "upi" | "card" | "wallet";
  cashbackPercent: number;
  maximumCashbackRupees: number | null;
  minimumAmountRupees: number;
  note: string;
};

// Adapted from the user's PayPack shopping offer seed. These are comparison
// estimates, never treated as a discount on the Razorpay order.
export const paymentRewards: PaymentReward[] = [
  { id: "sbi-cashback", method: "SBI Cashback Card", type: "card", cashbackPercent: 5, maximumCashbackRupees: null, minimumAmountRupees: 0, note: "Online shopping reward estimate" },
  { id: "jupiter-edge", method: "Jupiter Edge+ Card", type: "card", cashbackPercent: 5, maximumCashbackRupees: null, minimumAmountRupees: 0, note: "Online spend reward estimate" },
  { id: "kiwi-rupay", method: "Kiwi RuPay Card on UPI", type: "upi", cashbackPercent: 3, maximumCashbackRupees: 150, minimumAmountRupees: 200, note: "UPI-linked credit reward estimate" },
  { id: "axis-ace", method: "Axis Ace Card", type: "card", cashbackPercent: 2, maximumCashbackRupees: null, minimumAmountRupees: 0, note: "Online spend reward estimate" },
  { id: "icici-amazon", method: "ICICI Amazon Pay Card", type: "card", cashbackPercent: 2, maximumCashbackRupees: null, minimumAmountRupees: 0, note: "General online reward estimate" },
  { id: "hdfc-rupay", method: "HDFC RuPay Credit Card on UPI", type: "upi", cashbackPercent: 2, maximumCashbackRupees: 500, minimumAmountRupees: 200, note: "UPI purchase reward estimate" },
  { id: "yes-pay", method: "YES Pay UPI", type: "upi", cashbackPercent: 2, maximumCashbackRupees: 30, minimumAmountRupees: 200, note: "General merchant reward estimate" },
  { id: "kotak-811", method: "Kotak 811 UPI", type: "upi", cashbackPercent: 2, maximumCashbackRupees: 30, minimumAmountRupees: 200, note: "General merchant reward estimate" },
  { id: "bhim-upi", method: "BHIM UPI", type: "upi", cashbackPercent: 1, maximumCashbackRupees: 25, minimumAmountRupees: 100, note: "Base UPI reward estimate" },
  { id: "phonepe", method: "PhonePe UPI", type: "upi", cashbackPercent: 1, maximumCashbackRupees: 25, minimumAmountRupees: 100, note: "Illustrative UPI reward estimate" },
  { id: "paytm-wallet", method: "Paytm Wallet", type: "wallet", cashbackPercent: 1, maximumCashbackRupees: 25, minimumAmountRupees: 100, note: "Illustrative wallet reward estimate" },
];

export type RankedPaymentReward = PaymentReward & { estimatedRewardPaise: number };

export function rankPaymentRewards(amountPaise: number): RankedPaymentReward[] {
  const amountRupees = amountPaise / 100;
  return paymentRewards
    .filter((offer) => amountRupees >= offer.minimumAmountRupees)
    .map((offer) => {
      const raw = Math.round(amountPaise * offer.cashbackPercent / 100);
      const cap = offer.maximumCashbackRupees == null
        ? raw
        : offer.maximumCashbackRupees * 100;
      return { ...offer, estimatedRewardPaise: Math.min(raw, cap) };
    })
    .sort((left, right) => right.estimatedRewardPaise - left.estimatedRewardPaise || left.method.localeCompare(right.method));
}
