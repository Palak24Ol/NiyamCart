export const JOURNEY_API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export class JourneyError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function journeyApi<T>(path: string, body?: unknown, method?: string): Promise<T> {
  const response = await fetch(`${JOURNEY_API}${path}`, {
    method: method || (body === undefined ? "GET" : "POST"), credentials: "include",
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store",
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new JourneyError(typeof data.message === "string" ? data.message :
    typeof data.detail === "string" ? data.detail : "Please check the fields and try again.", response.status);
  return data as T;
}

export type BuyerMemory = {
  name: string; email?: string; phone: string; preferredLanguage: string; whatsappOptIn: boolean;
  use_for_agent: boolean; size: string; brands: string[]; budget_paise: number | null;
  rejected_product_ids: string[];
};
export const getBuyerMemory = () => journeyApi<BuyerMemory>("/api/customer/memory");
export async function updateBuyerMemory(patch: Partial<BuyerMemory>) {
  const current = await getBuyerMemory();
  const payload = { ...current, ...patch };
  delete payload.email;
  return journeyApi<BuyerMemory>("/api/customer/memory", payload, "PUT");
}

export type JourneyProduct = {
  id: string; name: string; brand: string; price_paise: number; image: string;
  stock: number; delivery_days: number; free_delivery: boolean; return_window_days: number;
};
export type Quote = {
  subtotal_paise: number; shipping_paise: number; total_paise: number;
  eta_max_days: number; estimated_arrival: string; delivery_source: string;
};
export type MissionRequest = {
  title: string; message: string; requirements: string[]; budget_paise: number | null;
  deadline: string | null; use_memory: boolean;
};
export type Mission = {
  id: string; status: string; revision: number; request: MissionRequest;
  messages: Array<{ role: string; text: string }>;
  plan: {
    questions?: string[]; groups?: Array<{ requirement: string; products: JourneyProduct[] }>;
    options?: Array<Quote & { product_ids: string[] }>; cart_id?: string;
    agent_status?: string; agent_answer?: string; memory_used?: boolean; size_note?: string;
  };
};
export type JourneyTask = {
  id: string; kind: "watch" | "replenish" | "recovery"; status: string;
  settings: { product_name?: string; target_paise?: number; interval_days?: number; order_id?: string };
  result: { message?: string; cart_id?: string; order_id?: string; quote?: Quote;
    unavailable?: Array<{ product_name: string; alternatives: JourneyProduct[] }> };
  next_run: string; expires_at: string; failures: number;
};
export type Notice = { id: string; title: string; body: string; href: string; read_at: string | null };
export type Dashboard = {
  missions: Mission[]; tasks: JourneyTask[]; notices: Notice[]; memory: BuyerMemory;
  scheduler: { enabled: boolean; interval_seconds: number; channel: string };
  fulfillment_connected: boolean; demo_fulfillment_enabled: boolean;
};
export type SupportCase = {
  id: string; order_id: string; kind: string; status: string;
  details: { message: string; product_id?: string; estimated_refund_paise?: number;
    price_difference_paise?: number; replacement?: JourneyProduct; delivery_source?: string };
};
export type CustomerOrder = {
  orderId: string; cartId: string; status: string; amountPaise: number; currency: string;
  paymentId: string | null; verifiedAt: string | null; createdAt: string; cartHash: string;
  shipment_status: string; shipment_source: string; estimated_arrival: string | null; is_late: boolean;
  events: Array<{ id: string; status: string; detail: string; source: string; occurred_at: string }>;
  items: Array<{ productId: string; name: string; image: string; quantity: number;
    unitPricePaise: number; return_eligible: boolean; return_deadline: string | null }>;
  cases: SupportCase[];
};
export const getCustomerOrders = () => journeyApi<{ items: CustomerOrder[] }>("/api/customer/orders");
export const dateLabel = (value: string) => new Date(
  /[zZ]$|[+-]\d\d:\d\d$/.test(value) || value.length === 10 ? value : `${value}Z`,
).toLocaleString("en-IN", value.length === 10 ? { dateStyle: "medium" } :
  { dateStyle: "medium", timeStyle: "short" });
