import type { PaymentReceipt } from "@/lib/checkout";

export type SavedOrderItem = {
  productId: string;
  name: string;
  image: string;
  quantity: number;
  unitPricePaise: number;
};

export type SavedOrder = PaymentReceipt & {
  ownerId: string;
  cartId: string;
  cartHash: string;
  items: SavedOrderItem[];
  whatsappStatus: string;
};

export type CustomerProfile = {
  name: string;
  email: string;
  phone: string;
  preferredLanguage: string;
  whatsappOptIn: boolean;
};

const OWNER_KEY = "niyamcart-customer-id";
const scopedKey = (base: string) => {
  if (!canUseStorage()) return `${base}:server`;
  return `${base}:${window.localStorage.getItem(OWNER_KEY) || "guest"}`;
};

export const emptyProfile: CustomerProfile = {
  name: "",
  email: "",
  phone: "",
  preferredLanguage: "English",
  whatsappOptIn: false,
};

const canUseStorage = () => typeof window !== "undefined";

export function loadSavedOrders(): SavedOrder[] {
  if (!canUseStorage()) return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(scopedKey("niyamcart-orders")) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveOrder(order: Omit<SavedOrder, "ownerId">) {
  if (!canUseStorage()) return;
  const ownerId = window.localStorage.getItem(OWNER_KEY);
  if (!ownerId) return;
  const existing = loadSavedOrders().filter((item) => item.orderId !== order.orderId);
  window.localStorage.setItem(
    scopedKey("niyamcart-orders"),
    JSON.stringify([{ ...order, ownerId }, ...existing].slice(0, 25)),
  );
}

export function updateOrderWhatsApp(orderId: string, whatsappStatus: string) {
  if (!canUseStorage()) return;
  const orders = loadSavedOrders().map((order) =>
    order.orderId === orderId ? { ...order, whatsappStatus } : order,
  );
  window.localStorage.setItem(scopedKey("niyamcart-orders"), JSON.stringify(orders));
}

export function loadCustomerProfile(): CustomerProfile {
  if (!canUseStorage()) return emptyProfile;
  try {
    const parsed = JSON.parse(window.localStorage.getItem(scopedKey("niyamcart-profile")) || "{}");
    return { ...emptyProfile, ...parsed };
  } catch {
    return emptyProfile;
  }
}

export function saveCustomerProfile(profile: CustomerProfile) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(scopedKey("niyamcart-profile"), JSON.stringify(profile));
}
