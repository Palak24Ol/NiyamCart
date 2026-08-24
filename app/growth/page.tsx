"use client";

import { ArrowLeft, BarChart3, ShieldCheck, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { formatMoney } from "@/lib/catalog";
import { getGrowthLedger, type GrowthLedger } from "@/lib/growth";

export default function GrowthPage() {
  const [ledger, setLedger] = useState<GrowthLedger | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { void getGrowthLedger().then(setLedger).catch((reason) => setError(reason instanceof Error ? reason.message : "Ledger unavailable.")); }, []);
  return <main className="growth-page">
    <section className="growth-ledger-shell">
      <header><div><span className="judge-badge">MERCHANT · TEST DEMO DATA</span><h1>Causal Growth Ledger</h1><p>Revenue uplift is counted only after a shown add-on is explicitly accepted.</p></div><Link href="/"><ArrowLeft size={16} /> Back to shop</Link></header>
      {error && <p className="checkout-error">{error}</p>}
      {!ledger ? <div className="ledger-loading">Loading merchant evidence…</div> : <>
        <div className="ledger-metrics">
          <article><BarChart3 size={20} /><small>Suggestion exposures</small><b>{ledger.exposures}</b></article>
          <article><ShieldCheck size={20} /><small>Accepted / rejected</small><b>{ledger.accepted} / {ledger.rejected}</b></article>
          <article><TrendingUp size={20} /><small>Acceptance rate</small><b>{ledger.acceptance_rate_percent}%</b></article>
          <article><TrendingUp size={20} /><small>Realised incremental revenue</small><b>{formatMoney(ledger.incremental_revenue_paise)}</b></article>
        </div>
        <section className="ledger-proof"><h2>Attribution rule</h2><p>Exposure creates no revenue claim. Rejection records zero uplift. Acceptance records only the deterministic difference between the baseline cart and selected bundle.</p><div><span>Accepted baseline</span><b>{formatMoney(ledger.baseline_revenue_paise)}</b></div><div><span>Assisted revenue</span><b>{formatMoney(ledger.assisted_revenue_paise)}</b></div><small><ShieldCheck size={13} /> Clearly labelled test/demo evidence—never presented as live merchant revenue.</small></section>
      </>}
    </section>
  </main>;
}
