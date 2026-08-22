export type AgentRun = {
  session_id: string;
  status: "completed" | "escalated" | "degraded" | "budget_exhausted" | "failed";
  answer: string;
  proposed_cart_id: string | null;
  step_count: number;
  revision_count: number;
  estimated_cost_microusd: number;
};

export type AgentEvent = {
  sequence: number;
  event_type: string;
  tool_name: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};

export type AgentAudit = {
  session_id: string;
  status: string;
  model: string;
  step_count: number;
  revision_count: number;
  estimated_cost_microusd: number;
  events: AgentEvent[];
};

export type VerifiedAudit = {
  scope_type: string;
  scope_id: string;
  valid: boolean;
  event_count: number;
  root_hash: string;
  events: Array<{
    sequence: number;
    event_type: string;
    payload: Record<string, unknown>;
    previous_hash: string;
    event_hash: string;
    created_at: string;
  }>;
};

export type AgentProduct = {
  product_id: string;
  name: string;
  price_paise: number;
  currency: string;
  stock: number;
  rating: number;
};

export type ProposedCart = {
  id: string;
  items: Array<{ product_id: string; quantity: number }>;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...init?.headers },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.message || body.detail || "Niyam could not complete that request.");
  }
  return body as T;
}

export const runAgent = (message: string) =>
  api<AgentRun>("/api/agent/sessions", {
    method: "POST",
    body: JSON.stringify({ message }),
  });

export const getAgentAudit = (sessionId: string) =>
  api<AgentAudit>(`/api/agent/sessions/${sessionId}/events`);

export const getVerifiedAudit = (sessionId: string) =>
  api<VerifiedAudit>(`/api/audit/agent_session/${sessionId}`);

export const getProposedCart = (cartId: string) =>
  api<ProposedCart>(`/api/carts/${cartId}`);

export function groundedProducts(events: AgentEvent[]): AgentProduct[] {
  const found = new Map<string, AgentProduct>();
  for (const event of events) {
    if (event.event_type !== "tool_result") continue;
    const candidates = Array.isArray(event.payload.products)
      ? event.payload.products
      : event.payload.product
        ? [event.payload.product]
        : [];
    for (const candidate of candidates) {
      if (!candidate || typeof candidate !== "object") continue;
      const product = candidate as Record<string, unknown>;
      if (
        typeof product.product_id === "string" &&
        typeof product.name === "string" &&
        typeof product.price_paise === "number"
      ) {
        found.set(product.product_id, product as unknown as AgentProduct);
      }
    }
  }
  return [...found.values()].slice(0, 5);
}
