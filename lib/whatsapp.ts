export type WhatsAppHandoff = {
  status: "ready_for_user_share" | "sending" | "sent" | "delivery_failed" | "disabled";
  duplicate: boolean;
  template_name: string | null;
  review_url: string | null;
  share_text: string | null;
  message: string;
  provider_message_id: string | null;
  destination_fingerprint: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function post<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.message || payload.detail || "The WhatsApp handoff is unavailable.");
  }
  return payload as T;
}

export const prepareWhatsAppReview = (cartId: string, cartHash: string, destination: string) =>
  post<WhatsAppHandoff>(`/api/carts/${cartId}/whatsapp-review`, {
    cart_hash: cartHash,
    destination,
    consent: true,
    destination_confirmed: true,
  });

export const prepareWhatsAppConfirmation = (orderId: string, destination: string) =>
  post<WhatsAppHandoff>(`/api/orders/${orderId}/whatsapp-confirmation`, {
    destination,
    consent: true,
    destination_confirmed: true,
  });
