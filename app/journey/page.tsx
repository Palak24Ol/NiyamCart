import { AccountShell } from "@/components/AccountShell";
import { JourneyPage } from "@/components/JourneyPage";
import { Suspense } from "react";

export default function Page() {
  return <AccountShell active="journey"><Suspense fallback={<p role="status">Loading your journey…</p>}><JourneyPage /></Suspense></AccountShell>;
}
