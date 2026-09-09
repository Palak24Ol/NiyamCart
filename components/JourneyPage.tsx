"use client";

import Link from "next/link";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowRight, Bell, Check, Clock3, Compass, LoaderCircle, Plus, RefreshCw, Sparkles } from "lucide-react";
import { formatMoney, products } from "@/lib/catalog";
import { dateLabel, journeyApi, JourneyError, updateBuyerMemory, type Dashboard, type Mission,
  type MissionRequest, type BuyerMemory, type JourneyProduct } from "@/lib/journey";
import { JourneyCheckout } from "@/components/JourneyCheckout";

type Tab = "missions" | "tasks" | "memory" | "activity" | "buyer";
const emptyRequest: MissionRequest = { title: "", message: "", requirements: [],
  budget_paise: null, deadline: null, use_memory: true };

export function JourneyPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [data, setData] = useState<Dashboard | null>(null);
  const [tab, setTab] = useState<Tab>("missions");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Mission | null>(null);
  const [form, setForm] = useState<MissionRequest>(emptyRequest);
  const cartId = data ? searchParams.get("cart") : null;
  const [watchProduct, setWatchProduct] = useState(products[0]?.id || "");
  const [watchPrice, setWatchPrice] = useState("");
  const [watchDays, setWatchDays] = useState(30);
  const [consent, setConsent] = useState(false);
  const [audit, setAudit] = useState<{ valid: boolean; event_count: number } | null>(null);
  const [buyerKey, setBuyerKey] = useState("");
  const [buyerExpiry, setBuyerExpiry] = useState("");
  const [buyerResult, setBuyerResult] = useState<{ review_url: string; total_paise: number } | null>(null);

  const refresh = useCallback(async () => setData(await journeyApi<Dashboard>("/api/journey")), []);
  useEffect(() => {
    let mounted = true;
    void journeyApi<Dashboard>("/api/journey").then(result => {
      if (!mounted) return;
      setData(result);
    }).catch((e: Error) => {
      if (!mounted) return;
      if (e instanceof JourneyError && e.status === 401) router.replace("/auth?next=" + encodeURIComponent(window.location.pathname + window.location.search));
      else setError(e.message);
    });
    const poll = window.setInterval(() => {
      if (!document.hidden) void refresh().catch(() => undefined);
    }, 30_000);
    return () => { mounted = false; window.clearInterval(poll); };
  }, [refresh, router]);

  async function act(work: () => Promise<unknown>, success = "") {
    setBusy(true); setError(""); setStatus("");
    try { await work(); await refresh(); setStatus(success); }
    catch (e) { setError(e instanceof Error ? e.message : "Please try again."); }
    finally { setBusy(false); }
  }

  async function saveAndPlan() {
    const request = { ...form, requirements: form.requirements.map(s => s.trim()).filter(Boolean) };
    const saved = await journeyApi<Mission>(editing ? `/api/journey/missions/${editing.id}` :
      "/api/journey/missions", editing ? { ...request, expected_revision: editing.revision } : request,
      editing ? "PUT" : "POST");
    setEditing(saved);
    const planned = await journeyApi<Mission>(`/api/journey/missions/${saved.id}/plan`,
      { expected_revision: saved.revision });
    setEditing(planned);
  }

  function openCart(id: string) {
    router.replace(`/journey?cart=${encodeURIComponent(id)}`, { scroll: false });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return <div className="journey">
    <section className="account-hero">
      <div><span className="kicker">YOUR SHOPPING, IN PROGRESS</span><h1>A little less to do.</h1>
        <p>Give Niyam a goal. Keep your options, watches and next steps together, wherever you sign in.</p></div>
      <div className="journey-live"><span className={data?.scheduler.enabled ? "live-dot" : ""} />
        {data ? data.scheduler.enabled ? "Watching while the store is online" : "Background checks paused" : "Connecting…"}</div>
    </section>
    {error && <div className="journey-alert" role="alert">{error}<button onClick={() => void act(refresh)}>Retry</button></div>}
    {status && <p className="journey-success" role="status"><Check size={16} />{status}</p>}
    {busy && <p className="journey-working" role="status"><LoaderCircle className="spin" size={17} />Working on your request…</p>}
    {cartId && <JourneyCheckout key={cartId} cartId={cartId} close={() => {
      router.replace("/journey", { scroll: false });
    }} />}
    <nav className="journey-tabs" aria-label="Shopping journey">
      {([['missions', 'Missions'], ['tasks', 'Watches & reminders'], ['memory', 'Buyer memory'],
        ['activity', `Updates${data?.notices.filter(n => !n.read_at).length ? ` (${data.notices.filter(n => !n.read_at).length})` : ''}`],
        ['buyer', 'AI buyer demo']] as Array<[Tab, string]>).map(([id, label]) =>
        <button key={id} aria-current={tab === id ? "page" : undefined} className={tab === id ? "selected" : ""}
          onClick={() => setTab(id)}>{label}</button>)}
    </nav>
    {!data && !error && <p className="orders-loading"><Clock3 size={20} />Loading your saved journey…</p>}
    {data && tab === "missions" && <div className="journey-columns">
      <section className="journey-panel journey-compose">
        <div className="journey-heading"><Compass size={21} /><h2>{editing ? "Refine your mission" : "Start with a goal"}</h2></div>
        <form onSubmit={e => { e.preventDefault(); void act(saveAndPlan, "Mission saved. Your latest plan is below."); }}>
          <label>Mission name<input required minLength={3} maxLength={120} value={form.title}
            onChange={e => setForm({ ...form, title: e.target.value })} placeholder="A fresh work wardrobe" /></label>
          <label>What are you shopping for?<textarea required minLength={3} maxLength={1000} rows={3}
            value={form.message} onChange={e => setForm({ ...form, message: e.target.value })}
            placeholder="I need comfortable pieces for the office. Keep the full basket within my budget." /></label>
          <label>Items to find, one per line<textarea rows={3} value={form.requirements.join("\n")}
            onChange={e => setForm({ ...form, requirements: e.target.value.split("\n").slice(0, 4) })}
            placeholder={"blue shirt\nblack shoes"} /></label>
          <small>Up to four item descriptions. Niyam will ask if a required detail is missing.</small>
          <div className="journey-fields"><label>Total budget (₹)<input type="number" min="1" max="100000" step="0.01"
            value={form.budget_paise === null ? "" : form.budget_paise / 100}
            onChange={e => setForm({ ...form, budget_paise: e.target.value ? Math.round(Number(e.target.value) * 100) : null })}
            placeholder="Including delivery" /></label>
            <label>Arrive by<input type="date" min={new Date().toISOString().slice(0, 10)} value={form.deadline || ""}
              onChange={e => setForm({ ...form, deadline: e.target.value || null })} /></label></div>
          <label className="journey-check"><input type="checkbox" checked={form.use_memory}
            onChange={e => setForm({ ...form, use_memory: e.target.checked })} />Use my enabled buyer memory</label>
          <div className="journey-actions"><button className="journey-primary" disabled={busy}><Sparkles size={16} />Save & plan</button>
            {editing && <button type="button" onClick={() => { setEditing(null); setForm(emptyRequest); }}>New mission</button>}</div>
        </form>
        <p className="journey-footnote">Delivery dates use the merchant catalogue’s conservative estimate. Carrier guarantees are not connected.</p>
      </section>
      <section className="journey-missions" aria-label="Saved missions">
        {!data.missions.length && <div className="journey-empty"><Compass size={32} /><h2>Your next purchase starts here</h2>
          <p>Save a mission once. Come back to compare, refine and check out when you’re ready.</p></div>}
        {data.missions.map(mission => <article key={mission.id} className="journey-panel">
          <div className="journey-heading"><span className="journey-badge">{mission.status.replaceAll("_", " ")}</span>
            <button disabled={busy} onClick={() => { setEditing(mission); setForm(mission.request); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Edit goal</button></div>
          <h2>{mission.request.title}</h2><p>{mission.request.message}</p>
          {mission.status === "planning" && <p role="status" className="journey-question">Checking your items, budget and delivery date. If the AI service times out, catalogue checks will prepare the results. Your goal is saved if you leave this page.</p>}
          <div className="journey-meta"><span>{mission.request.budget_paise ? formatMoney(mission.request.budget_paise) : "Budget to confirm"}</span>
            {mission.request.deadline && <span>By {dateLabel(mission.request.deadline)}</span>}
            {mission.plan.memory_used && <span>Buyer memory used</span>}</div>
          {mission.plan.questions?.map(question => <p className="journey-question" key={question}>{question}</p>)}
          {mission.status !== "planning" && !mission.plan.options?.length && mission.plan.groups?.map(group =>
            <div className="journey-option" key={group.requirement}><b>{group.requirement}</b>
              <p>{group.products.length ? `${group.products.length} catalogue matches found, but no complete basket fits all requirements.` : "No in-stock catalogue match meets this description and delivery date. Try another colour or item description."}</p>
              {group.products.slice(0, 2).map(product => <p key={product.id}>{product.name} · {formatMoney(product.price_paise)}</p>)}
            </div>)}
          {mission.plan.agent_status && <p className="journey-footnote">{mission.plan.agent_status === "degraded" ?
            "AI provider unavailable · catalogue rules prepared these options" : "Bounded agent research + verified catalogue checks"}</p>}
          {mission.plan.options?.map((option, index) => <div className="journey-option" key={option.product_ids.join(",")}>
            <div className="journey-heading"><b>{index === 0 ? "Lowest total" : `Alternative ${index}`}</b><strong>{formatMoney(option.total_paise)}</strong></div>
            {option.product_ids.map(id => {
              const product = mission.plan.groups?.flatMap(g => g.products).find(p => p.id === id);
              return product && <div className="journey-product" key={id}><Image src={product.image} alt="" width={48} height={58} unoptimized /><span>{product.name}<small>{formatMoney(product.price_paise)}</small></span>
                <button disabled={busy} title="Remember that you don't want this product" onClick={() => void act(() =>
                  updateBuyerMemory({ rejected_product_ids: [...new Set([...data.memory.rejected_product_ids, id])] }),
                "Preference saved. Enable buyer memory and replan to apply it.")}>Not for me</button></div>;
            })}
            <small>Delivery {formatMoney(option.shipping_paise)} · Estimated by {dateLabel(option.estimated_arrival)}</small>
            <button className="journey-primary" disabled={busy} onClick={() => void act(async () => {
              const result = await journeyApi<{ cart_id: string }>(`/api/journey/missions/${mission.id}/select`,
                { expected_revision: mission.revision, product_ids: option.product_ids }); openCart(result.cart_id);
            })}>Review this basket <ArrowRight size={16} /></button>
          </div>)}
          {!!mission.plan.options?.length && <p className="journey-footnote">{mission.plan.size_note}</p>}
          <div className="journey-actions"><button disabled={busy} onClick={() => void act(() =>
            journeyApi(`/api/journey/missions/${mission.id}/plan`, { expected_revision: mission.revision }))}><RefreshCw size={14} />Refresh plan</button>
            <button disabled={busy} onClick={() => void act(async () => setAudit(await journeyApi(
              `/api/journey/missions/${mission.id}/audit`)))}>Verify activity trail</button></div>
          <details><summary>Conversation history</summary>{mission.messages.map((m, i) => <p key={i}><b>{m.role === "buyer" ? "You" : "Niyam"}:</b> {m.text}</p>)}</details>
        </article>)}
        {audit && <p role="status">Activity trail {audit.valid ? "verified" : "could not be verified"} · {audit.event_count} events</p>}
      </section>
    </div>}
    {data && tab === "tasks" && <div className="journey-columns">
      <section className="journey-panel">
        <div className="journey-heading"><Bell size={21} /><h2>Watch for the right moment</h2></div>
        <form onSubmit={e => { e.preventDefault(); void act(() => journeyApi("/api/journey/tasks", {
          kind: "watch", product_id: watchProduct, target_paise: watchPrice ? Math.round(Number(watchPrice) * 100) : null,
          expires_at: new Date(Date.now() + watchDays * 86_400_000).toISOString(), consent,
        }), "Watch saved. We’ll post here when your conditions match."); }}>
          <label>Product<select value={watchProduct} onChange={e => setWatchProduct(e.target.value)}>
            {products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
          <label>Maximum total including delivery (₹)<input type="number" min="1" max="100000" step="0.01"
            value={watchPrice} onChange={e => setWatchPrice(e.target.value)} placeholder="Leave blank to watch at today's total" /></label>
          <label>Watch for (days)<input type="number" min="1" max="365" value={watchDays}
            onChange={e => setWatchDays(Number(e.target.value))} /></label>
          <label className="journey-check"><input required type="checkbox" checked={consent}
            onChange={e => setConsent(e.target.checked)} />Check availability and price; post updates in my account</label>
          <button className="journey-primary" disabled={busy}><Plus size={16} />Create watch</button>
        </form><p className="journey-footnote">Checks run every 15 minutes while the backend is online, and catch up after a restart. Updates stay in your account. Set reorder reminders from <Link href="/orders">My orders</Link>.</p>
      </section>
      <section aria-label="Your watches and reminders">
        {!data.tasks.length && <div className="journey-empty"><Bell size={30} /><h2>No watches yet</h2><p>Keep an eye on a product or schedule your next purchase.</p></div>}
        {data.tasks.map(task => <article className="journey-panel" key={task.id}>
          <div className="journey-heading"><span className="journey-badge">{task.kind}</span><small>{task.status.replaceAll("_", " ")}</small></div>
          <h2>{task.settings.product_name || (task.kind === "replenish" ? "Your next repeat purchase" : "Recover your checkout")}</h2>
          <p>{task.result.message || "Scheduled and ready to check."}</p>
          <small>Next check: {dateLabel(task.next_run)} · Expires {dateLabel(task.expires_at)}</small>
          {task.result.unavailable?.map(item => <div key={item.product_name}><p>{item.product_name} is unavailable.</p>
            {item.alternatives.map((alternative: JourneyProduct) => <p key={alternative.id}>{alternative.name} · {formatMoney(alternative.price_paise)}</p>)}</div>)}
          <div className="journey-actions">
            {task.result.cart_id && <button className="journey-primary" onClick={() => openCart(task.result.cart_id!)}>Review basket</button>}
            {task.result.order_id && <Link href={`/orders?order=${task.result.order_id}`}>Check order status</Link>}
            {!['completed', 'cancelled', 'expired'].includes(task.status) && <>
              <button disabled={busy} onClick={() => void act(() => journeyApi(`/api/journey/tasks/${task.id}/action`,
                { action: task.status === "paused" || task.status === "needs_attention" ? "resume" : "pause" }))}>{task.status === "paused" || task.status === "needs_attention" ? "Resume" : "Pause"}</button>
              {['active', 'awaiting_review'].includes(task.status) && <button disabled={busy} onClick={() => void act(() => journeyApi(`/api/journey/tasks/${task.id}/action`, { action: "check" }))}>Check now</button>}
              <button disabled={busy} onClick={() => void act(() => journeyApi(`/api/journey/tasks/${task.id}/action`, { action: "cancel" }))}>Stop</button>
            </>}
          </div>
        </article>)}
      </section>
    </div>}
    {data && tab === "memory" && <MemoryEditor key={JSON.stringify(data.memory)} memory={data.memory} busy={busy} save={patch =>
      void act(() => updateBuyerMemory(patch), "Buyer memory saved across your devices.")} forget={() =>
      void act(() => journeyApi("/api/customer/memory/forget", {}), "Saved buyer preferences cleared.")} />}
    {data && tab === "activity" && <section className="journey-feed">
      {!data.notices.length && <div className="journey-empty"><Bell size={30} /><h2>All quiet for now</h2><p>Price matches, delivery updates and tasks needing your attention appear here.</p></div>}
      {data.notices.map(notice => <article className={`journey-panel ${notice.read_at ? "is-read" : ""}`} key={notice.id}>
        <h2>{notice.title}</h2><p>{notice.body}</p><div className="journey-actions"><Link href={notice.href}>View details <ArrowRight size={15} /></Link>
          {!notice.read_at && <button disabled={busy} onClick={() => void act(() => journeyApi(`/api/journey/notices/${notice.id}/read`, {}))}>Mark read</button>}</div>
      </article>)}
    </section>}
    {data && tab === "buyer" && <section className="journey-panel journey-demo">
      <span className="kicker">EXTERNAL BUYER HANDOFF</span><h2>Let another AI prepare your basket.</h2>
      <p>A separate buyer can discover the catalogue and policies, request a price-checked basket, and return it here for your approval.</p>
      <p className="journey-footnote">Custom NiyamCart demonstration API. Quote access only; no order creation or payment permission. Keys expire after 15 minutes.</p>
      <div className="journey-actions"><button className="journey-primary" disabled={busy} onClick={() => void act(async () => {
        const result = await journeyApi<{ key: string; expires_at: string }>("/api/journey/buyer-key", {});
        setBuyerKey(result.key); setBuyerExpiry(result.expires_at); setBuyerResult(null);
      })}>Create temporary buyer key</button>
        {buyerKey && <button disabled={busy} onClick={() => void act(async () => {
          await journeyApi("/api/journey/buyer-key/revoke", {}); setBuyerKey("");
        }, "Buyer access revoked.")}>Revoke access</button>}</div>
      {buyerKey && <><label>Temporary key<input readOnly type="password" value={buyerKey} autoComplete="off" /></label>
        <small>Expires {dateLabel(buyerExpiry)}. The key is kept only in this page’s memory.</small>
        <div className="journey-actions"><button onClick={() => void act(() => navigator.clipboard.writeText(buyerKey), "Key copied.")}>Copy key for external client</button>
          <button disabled={busy} onClick={() => void act(async () => {
            const { JOURNEY_API } = await import("@/lib/journey");
            const contract = await fetch(`${JOURNEY_API}/.well-known/buyer-commerce.json`).then(r => r.json());
            const catalog = await fetch(`${JOURNEY_API}${contract.catalog}`).then(r => r.json());
            const product = catalog.products.find((p: { availability: { quantity: number } }) => p.availability?.quantity > 0);
            if (!product) throw new Error("No in-stock product is available for the demo.");
            const response = await fetch(`${JOURNEY_API}${contract.quote}`, { method: "POST",
              headers: { "content-type": "application/json", authorization: `Bearer ${buyerKey}` },
              body: JSON.stringify({ product_ids: [product.product_id], budget_paise: 10_000_000, request_key: crypto.randomUUID() }) });
            const result = await response.json(); if (!response.ok) throw new Error(result.message || "Quote request failed");
            setBuyerResult(result);
          })}>Run discovery → quote demo</button></div></>}
      {buyerResult && <p className="journey-success">Quote prepared: {formatMoney(buyerResult.total_paise)}.
        <Link href={buyerResult.review_url}>Review basket</Link></p>}
    </section>}
  </div>;
}

function MemoryEditor({ memory, busy, save, forget }: { memory: BuyerMemory; busy: boolean;
  save: (value: Partial<BuyerMemory>) => void; forget: () => void }) {
  const [draft, setDraft] = useState(memory);
  return <section className="journey-panel journey-memory"><h2>Remember the things that help.</h2>
    <p>Choose what Niyam can use in future missions. Current mission details take priority.</p>
    <form onSubmit={e => { e.preventDefault(); save({ ...draft, brands: draft.brands.filter(Boolean) }); }}>
      <label className="journey-check"><input type="checkbox" checked={draft.use_for_agent}
        onChange={e => setDraft({ ...draft, use_for_agent: e.target.checked })} />Allow Niyam to use these preferences when planning</label>
      <div className="journey-fields"><label>Usual size<input maxLength={30} value={draft.size}
        onChange={e => setDraft({ ...draft, size: e.target.value })} placeholder="M, UK 8…" /></label>
        <label>Usual total budget (₹)<input type="number" min="1" max="100000" value={draft.budget_paise ? draft.budget_paise / 100 : ""}
          onChange={e => setDraft({ ...draft, budget_paise: e.target.value ? Math.round(Number(e.target.value) * 100) : null })} /></label></div>
      <label>Preferred brands, separated by commas<input value={draft.brands.join(", ")}
        onChange={e => setDraft({ ...draft, brands: e.target.value.split(",").map(s => s.trim()) })} /></label>
      <small>Size is advisory until the merchant supplies stock for each size. Brand preferences affect candidate ranking.</small>
      <p>{draft.rejected_product_ids.length} products marked “not for me”.</p>
      <div className="journey-actions"><button className="journey-primary" disabled={busy}>Save memory</button>
        <button type="button" disabled={busy} onClick={() => setDraft({ ...draft, rejected_product_ids: [] })}>Clear rejected products</button>
        <button type="button" disabled={busy} onClick={forget}>Forget saved preferences</button></div>
    </form><p className="journey-footnote">Forgetting preferences does not erase your existing missions or payment audit history.</p>
  </section>;
}
