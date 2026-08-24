import type { Metadata } from "next";
import { AccountShell } from "@/components/AccountShell";
import { ProfilePage } from "@/components/ProfilePage";

export const metadata: Metadata = { title: "Profile — NiyamCart" };

export default function ProfileRoute() {
  return <AccountShell active="profile"><ProfilePage /></AccountShell>;
}
