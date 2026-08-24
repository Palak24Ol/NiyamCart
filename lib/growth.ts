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
