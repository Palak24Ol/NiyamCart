import type { Metadata } from "next";
import { AuthPage } from "@/components/AuthPage";

export const metadata: Metadata = { title: "Login or Sign Up — NiyamCart" };

export default function AuthenticationPage() {
  return <AuthPage />;
}
