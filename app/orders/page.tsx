import type { Metadata } from "next";
import { AccountShell } from "@/components/AccountShell";
import { MyOrdersPage } from "@/components/MyOrdersPage";

export const metadata: Metadata = { title: "My Orders — NiyamCart" };

export default function OrdersPage() {
  return <AccountShell active="orders"><MyOrdersPage /></AccountShell>;
}
