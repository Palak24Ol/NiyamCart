export type CompatibleAddon = {
  product_id: string;
  rule_id: string;
  reason: string;
};

export type CompatibleAddonResponse = {
  primary_product_id: string;
  items: CompatibleAddon[];
  count: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function getCompatibleAddons(productId: string, limit = 3) {
  const response = await fetch(
    `${API_BASE}/api/products/${encodeURIComponent(productId)}/compatible-addons?limit=${limit}`,
  );
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.message || body.detail || "Compatible products are unavailable.");
  }
  return body as CompatibleAddonResponse;
}

export type GrowthEventType = "exposed" | "accepted" | "rejected";

export async function recordGrowthEvent(payload: {
  session_id?: string | null;
  cart_id?: string | null;
  primary_product_id: string;
  addon_product_id: string;
  event_type: GrowthEventType;
  baseline_paise: number;
  suggested_paise: number;
}) {
  const response = await fetch(`${API_BASE}/api/growth/events`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Growth evidence could not be recorded.");
  return response.json();
}

export type GrowthLedger = {
  data_mode: "test_demo";
  exposures: number;
  accepted: number;
  rejected: number;
  acceptance_rate_percent: number;
  baseline_revenue_paise: number;
  assisted_revenue_paise: number;
  incremental_revenue_paise: number;
};

export async function getGrowthLedger() {
  const response = await fetch(`${API_BASE}/api/growth/ledger`);
  if (!response.ok) throw new Error("Growth ledger is unavailable.");
  return response.json() as Promise<GrowthLedger>;
}
