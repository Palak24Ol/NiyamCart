export type ApprovalCart = {
  id: string;
  cart_hash: string;
  total_paise: number;
  expires_at: string;
};

type CartLineInput = { productId: string; quantity: number };

export type CompatibilityClaim = {
  primaryProductId: string;
  addonProductId: string;
};

export type PaymentReceipt = {
  status: string;
  orderId: string;
  paymentId: string;
  amountPaise: number;
  currency: string;
  verifiedAt: string;
  testMode: true;
};

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
    credentials: "include",
    headers: { "content-type": "application/json", ...init?.headers },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.message || body.detail || "The checkout request could not be completed.");
  }
  return body as T;
}

export async function prepareCartForApproval(
  lines: CartLineInput[],
  compatibilityClaims: CompatibilityClaim[] = [],
): Promise<ApprovalCart> {
  const proposed = await api<{ id: string }>("/api/carts", {
    method: "POST",
    body: JSON.stringify({
      items: lines.map((line) => ({
        product_id: line.productId,
        quantity: line.quantity,
      })),
      compatibility_claims: compatibilityClaims.map((claim) => ({
        primary_product_id: claim.primaryProductId,
        addon_product_id: claim.addonProductId,
      })),
    }),
  });
  const frozen = await api<ApprovalCart>(`/api/carts/${proposed.id}/freeze`, { method: "POST" });
  if (!frozen.cart_hash) throw new Error("The cart could not be locked for approval.");
  return frozen;
}

export type DeliveryAddress = {
  id: string;
  label: string;
  recipient_name: string;
  phone: string;
  line1: string;
  locality: string;
  landmark: string | null;
  city: string;
  state: string;
  pincode: string;
  latitude: number | null;
  longitude: number | null;
  is_default: boolean;
};

export type DeliveryQuote = {
  address_id: string;
  address_label: string;
  city: string;
  masked_pincode: string;
  delivery_paise: number;
  eta_min_days: number;
  eta_max_days: number;
  confirmed_at: string;
};

export type PaymentOffer = {
  key: string;
  code: string | null;
  title: string;
  payment_method: string;
  terms: string;
  savings_paise: number;
  expected_payable_paise: number;
  eligible: boolean;
  provider_configured: boolean;
  status: "available" | "preview" | "ineligible" | "standard";
  reason: string;
};

export async function createCheckoutCart(
  lines: CartLineInput[],
  compatibilityClaims: CompatibilityClaim[] = [],
) {
  return api<{ id: string; total_paise: number }>("/api/carts", {
    method: "POST",
    body: JSON.stringify({
      items: lines.map((line) => ({ product_id: line.productId, quantity: line.quantity })),
      compatibility_claims: compatibilityClaims.map((claim) => ({
        primary_product_id: claim.primaryProductId,
        addon_product_id: claim.addonProductId,
      })),
    }),
  });
}

export const getAddresses = async () => {
  const response = await api<{ items: DeliveryAddress[] }>("/api/customer/addresses");
  return response.items;
};

export const saveAddress = (address: Omit<DeliveryAddress, "id">, addressId?: string) =>
  api<DeliveryAddress>(addressId ? `/api/customer/addresses/${addressId}` : "/api/customer/addresses", {
    method: addressId ? "PUT" : "POST",
    body: JSON.stringify(address),
  });

export const confirmDelivery = (cartId: string, addressId: string) =>
  api<DeliveryQuote>(`/api/carts/${cartId}/delivery`, {
    method: "POST",
    body: JSON.stringify({ address_id: addressId, confirmed: true }),
  });

export const reverseGeocode = (
  latitude: number,
  longitude: number,
  allowPublicProvider = false,
) =>
  api<{
    line1: string;
    locality: string;
    city: string;
    state: string;
    pincode: string;
    latitude: number;
    longitude: number;
    approximate: true;
  }>("/api/location/reverse-geocode", {
    method: "POST",
    body: JSON.stringify({ latitude, longitude, allow_public_provider: allowPublicProvider }),
  });

export const getPaymentOffers = async (cartId: string) =>
  api<{ items: PaymentOffer[]; best_offer_key: string }>(`/api/carts/${cartId}/payment-offers`);

export const selectPaymentOffer = (
  cartId: string,
  offerKey: string,
  preferredPaymentMethod: "any" | "upi" | "card" | "netbanking" | "wallet" = "any",
) =>
  api(`/api/carts/${cartId}/payment-offer`, {
    method: "POST",
    body: JSON.stringify({
      offer_key: offerKey,
      preferred_payment_method: preferredPaymentMethod,
      confirmed: true,
    }),
  });

export const finalizeCheckoutCart = (cartId: string) =>
  api<ApprovalCart>(`/api/carts/${cartId}/finalize`, { method: "POST" });

export type CartRescue = {
  previous_cart_id: string;
  replacement_cart_id: string;
  previous_approval_revoked: boolean;
  intent_preserved: boolean;
  price_delta_paise: number;
  requires_new_review_and_approval: boolean;
  data_mode: string;
  changes: Array<{
    old_product_name: string;
    new_product_name: string;
    old_price_paise: number;
    new_price_paise: number;
    reason: string;
  }>;
};

export const demonstrateCartRescue = (cartId: string) =>
  api<CartRescue>(`/api/carts/${cartId}/rescue`, {
    method: "POST",
    body: JSON.stringify({ simulate_inventory_change: true }),
  });

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

export async function approveAndOpenCheckout(
  approval: ApprovalCart,
): Promise<PaymentReceipt> {
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
  return openExistingOrderCheckout(order.id);
}

export async function openExistingOrderCheckout(orderId: string, resume = false): Promise<PaymentReceipt> {
  const checkout = await api<RazorpayCheckout>(
    resume ? `/api/customer/orders/${orderId}/resume` : `/api/orders/${orderId}/razorpay-checkout`,
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
          const verified = await api<{
            status: string;
            internal_order_id: string;
            razorpay_payment_id: string;
            amount_paise: number;
            currency: string;
            verified_at: string;
            test_mode: true;
          }>("/api/payments/razorpay/verify", {
            method: "POST",
            body: JSON.stringify({
              internal_order_id: checkout.internal_order_id,
              razorpay_order_id: payment.razorpay_order_id,
              razorpay_payment_id: payment.razorpay_payment_id,
              razorpay_signature: payment.razorpay_signature,
            }),
          });
          resolve({
            status: verified.status,
            orderId: verified.internal_order_id,
            paymentId: verified.razorpay_payment_id,
            amountPaise: verified.amount_paise,
            currency: verified.currency,
            verifiedAt: verified.verified_at,
            testMode: verified.test_mode,
          });
        } catch (error) {
          reject(error);
        }
      },
    });
    instance.open();
  });
}
