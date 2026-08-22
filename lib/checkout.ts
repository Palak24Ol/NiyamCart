export type ApprovalCart = {
  id: string;
  cart_hash: string;
  total_paise: number;
  expires_at: string;
};

type CartLineInput = { productId: string; quantity: number };

type RazorpayCheckout = {
  internal_order_id: string;
  razorpay_order_id: string;
  key_id: string;
  amount_paise: number;
  currency: string;
  merchant_name: string;
  description: string;
  test_mode: true;
};

type RazorpaySuccess = {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
};

type RazorpayOptions = {
  key: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  order_id: string;
  handler: (response: RazorpaySuccess) => void | Promise<void>;
  modal: { ondismiss: () => void };
  theme: { color: string };
};

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayOptions) => { open: () => void };
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...init?.headers },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.message || body.detail || "The checkout request could not be completed.");
  }
  return body as T;
}

export async function prepareCartForApproval(lines: CartLineInput[]): Promise<ApprovalCart> {
  const proposed = await api<{ id: string }>("/api/carts", {
    method: "POST",
    body: JSON.stringify({
      items: lines.map((line) => ({
        product_id: line.productId,
        quantity: line.quantity,
      })),
    }),
  });
  const frozen = await api<ApprovalCart>(`/api/carts/${proposed.id}/freeze`, {
    method: "POST",
  });
  if (!frozen.cart_hash) throw new Error("The cart could not be locked for approval.");
  return frozen;
}

function loadRazorpayCheckout(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>("script[data-niyamcart-razorpay]");
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("Razorpay Checkout failed to load.")), {
        once: true,
      });
      return;
    }
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.dataset.niyamcartRazorpay = "true";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Razorpay Checkout failed to load."));
    document.head.appendChild(script);
  });
}

export async function approveAndOpenCheckout(approval: ApprovalCart): Promise<string> {
  await api(`/api/carts/${approval.id}/approve`, {
    method: "POST",
    body: JSON.stringify({ cart_hash: approval.cart_hash }),
  });
  const order = await api<{ id: string }>("/api/orders", {
    method: "POST",
    body: JSON.stringify({
      cart_id: approval.id,
      cart_hash: approval.cart_hash,
      idempotency_key: `checkout-${approval.id}`,
    }),
  });
  const checkout = await api<RazorpayCheckout>(
    `/api/orders/${order.id}/razorpay-checkout`,
    { method: "POST" },
  );
  await loadRazorpayCheckout();
  if (!window.Razorpay) throw new Error("Razorpay Checkout is unavailable.");

  return new Promise((resolve, reject) => {
    let submitted = false;
    const instance = new window.Razorpay!({
      key: checkout.key_id,
      amount: checkout.amount_paise,
      currency: checkout.currency,
      name: checkout.merchant_name,
      description: checkout.description,
      order_id: checkout.razorpay_order_id,
      theme: { color: "#176b4c" },
      modal: {
        ondismiss: () => {
          if (!submitted) reject(new Error("Checkout was closed. Your cart was not marked paid."));
        },
      },
      handler: async (payment) => {
        submitted = true;
        try {
          const verified = await api<{ status: string }>("/api/payments/razorpay/verify", {
            method: "POST",
            body: JSON.stringify({
              internal_order_id: checkout.internal_order_id,
              razorpay_order_id: payment.razorpay_order_id,
              razorpay_payment_id: payment.razorpay_payment_id,
              razorpay_signature: payment.razorpay_signature,
            }),
          });
          resolve(verified.status);
        } catch (error) {
          reject(error);
        }
      },
    });
    instance.open();
  });
}
