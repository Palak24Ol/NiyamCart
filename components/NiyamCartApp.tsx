"use client";

import {
  ArrowRight,
  Bot,
  Check,
  ChevronDown,
  CircleHelp,
  CircleCheckBig,
  CircleX,
  Copy,
  LoaderCircle,
  MessageCircle,
  Minus,
  Plus,
  Search,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Star,
  Trash2,
  UserRound,
  Wrench,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import { formatMoney, products, type Product } from "@/lib/catalog";
import {
  getAgentAudit,
  getProposedCart,
  getVerifiedAudit,
  groundedProducts,
  runAgent,
  type AgentAudit,
  type AgentRun,
  type VerifiedAudit,
} from "@/lib/agent";
import {
  approveAndOpenCheckout,
  prepareCartForApproval,
  type ApprovalCart,
} from "@/lib/checkout";
import {
  prepareWhatsAppConfirmation,
  prepareWhatsAppReview,
  type WhatsAppHandoff,
} from "@/lib/whatsapp";

type Cart = Record<string, number>;

const suggestions = [
  "Build a festive outfit under ₹1,500",
  "Find a face serum under ₹500",
  "Compare office-ready looks",
];

export function NiyamCartApp() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [cart, setCart] = useState<Cart>({});
  const [cartOpen, setCartOpen] = useState(false);
  const [agentOpen, setAgentOpen] = useState(true);
  const [agentQuery, setAgentQuery] = useState("");
  const [agentAnswer, setAgentAnswer] = useState<string | null>(null);
  const [agentRun, setAgentRun] = useState<AgentRun | null>(null);
  const [agentAudit, setAgentAudit] = useState<AgentAudit | null>(null);
  const [verifiedAudit, setVerifiedAudit] = useState<VerifiedAudit | null>(null);
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [visibleCount, setVisibleCount] = useState(12);

  const categories = ["All", ...Array.from(new Set(products.map((item) => item.category)))];
  const visibleProducts = products.filter((item) => {
    const matchesCategory = category === "All" || item.category === category;
    const haystack = `${item.name} ${item.description} ${item.tags.join(" ")}`.toLowerCase();
    return matchesCategory && haystack.includes(query.toLowerCase());
  });
  const displayedProducts = visibleProducts.slice(0, visibleCount);

  const cartLines = useMemo(
    () =>
      products
        .filter((product) => cart[product.id])
        .map((product) => ({ product, quantity: cart[product.id] })),
    [cart],
  );
  const cartCount = cartLines.reduce((sum, line) => sum + line.quantity, 0);
  const subtotal = cartLines.reduce(
    (sum, line) => sum + line.product.pricePaise * line.quantity,
    0,
  );

  const updateCart = (id: string, delta: number) => {
    setCart((current) => {
      const next = Math.max(0, (current[id] || 0) + delta);
      const updated = { ...current, [id]: next };
      if (!next) delete updated[id];
      return updated;
    });
  };

  const askAgent = async (prompt = agentQuery) => {
    if (!prompt.trim()) return;
    setAgentQuery(prompt);
    setAgentLoading(true);
    setAgentError(null);
    setAgentAnswer(null);
    setAgentRun(null);
    setAgentAudit(null);
    setVerifiedAudit(null);
    try {
      const result = await runAgent(prompt.trim());
      setAgentRun(result);
      setAgentAnswer(result.answer);
      const [events, audit] = await Promise.all([
        getAgentAudit(result.session_id),
        getVerifiedAudit(result.session_id),
      ]);
      setAgentAudit(events);
      setVerifiedAudit(audit);
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Niyam is temporarily unavailable.");
    } finally {
      setAgentLoading(false);
    }
  };

  const reviewAgentCart = async () => {
    if (!agentRun?.proposed_cart_id) return;
    setAgentError(null);
    try {
      const proposed = await getProposedCart(agentRun.proposed_cart_id);
      setCart(Object.fromEntries(proposed.items.map((item) => [item.product_id, item.quantity])));
      setCartOpen(true);
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "The proposed cart is unavailable.");
    }
  };

  const recommendations = groundedProducts(agentAudit?.events || []);
  const visibleAgentEvents = (agentAudit?.events || []).filter(
    (event) => event.event_type !== "model_response" && event.event_type !== "user_message",
  );

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="#top" aria-label="NiyamCart home">
          <span className="brand-mark"><Check size={18} strokeWidth={3} /></span>
          <span>NiyamCart</span>
        </a>
        <nav className="desktop-nav" aria-label="Main navigation">
          <a className="active" href="#shop">Shop</a>
          <a href="#agent">AI assistant</a>
          <a href="#trust">How it works</a>
        </nav>
        <div className="header-actions">
          <button className="icon-button" aria-label="Help"><CircleHelp size={20} /></button>
          <button className="cart-button" onClick={() => setCartOpen(true)}>
            <ShoppingBag size={19} />
            <span>Cart</span>
            {cartCount > 0 && <b>{cartCount}</b>}
          </button>
          <button className="avatar" aria-label="Account"><UserRound size={19} /></button>
        </div>
      </header>

      <main id="top">
        <section className="hero">
          <div className="hero-copy">
            <div className="eyebrow"><Sparkles size={15} /> Bounded AI commerce</div>
            <h1>Shop smarter.<br /><em>Stay in control.</em></h1>
            <p>Tell Niyam what you need. It compares the catalog, explains every recommendation and builds a cart that only you can approve.</p>
            <div className="hero-actions">
              <button className="primary-button" onClick={() => setAgentOpen(true)}>
                Ask Niyam <ArrowRight size={18} />
              </button>
              <a className="text-link" href="#shop">Browse products</a>
            </div>
            <div className="trust-row">
              <span><ShieldCheck size={17} /> No surprise purchases</span>
              <span><Check size={17} /> You approve the exact cart</span>
            </div>
          </div>

          <div className="hero-card" aria-label="Example Niyam recommendation">
            <div className="agent-orb"><Bot size={27} /></div>
            <span className="mini-label">Niyam recommends</span>
            <h2>Your festive pairing</h2>
            <p>Two coordinated, highly rated products that stay comfortably below ₹1,500.</p>
            <div className="bundle-items">
              <div><img src="/catalog/P-001.webp" alt="" /><p><b>Floral Cotton Kurta</b><small>Everyday comfort</small></p><strong>₹349</strong></div>
              <div><img src="/catalog/P-351.webp" alt="" /><p><b>Pearl Drop Earrings</b><small>Coordinated add-on</small></p><strong>₹129</strong></div>
            </div>
            <div className="bundle-total"><span>Total</span><b>₹478</b></div>
            <button onClick={() => { setCart({ "P-001": 1, "P-351": 1 }); setCartOpen(true); }}>
              Review this cart <ArrowRight size={17} />
            </button>
            <small className="approval-note"><ShieldCheck size={14} /> Nothing is purchased until you approve</small>
          </div>
        </section>

        <section className="shop-section" id="shop">
          <div className="section-heading">
            <div><span className="kicker">CURATED FOR REAL LIFE</span><h2>Products worth choosing</h2></div>
            <p>Explore 500 products across 10 categories with clear details and explainable recommendations.</p>
          </div>

          <div className="shop-tools">
            <label className="search-box">
              <Search size={19} />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search products or needs" />
              {query && <button onClick={() => setQuery("")} aria-label="Clear search"><X size={16} /></button>}
            </label>
            <div className="category-tabs">
              {categories.map((item) => (
                <button className={category === item ? "selected" : ""} onClick={() => { setCategory(item); setVisibleCount(12); }} key={item}>{item}</button>
              ))}
            </div>
            <button className="sort-button">Recommended <ChevronDown size={16} /></button>
          </div>

          <div className="product-grid">
            {displayedProducts.map((product) => (
              <ProductCard product={product} quantity={cart[product.id] || 0} updateCart={updateCart} key={product.id} />
            ))}
          </div>
          {displayedProducts.length < visibleProducts.length && (
            <button className="load-more" onClick={() => setVisibleCount((count) => count + 12)}>
              Show more products <span>{displayedProducts.length} of {visibleProducts.length}</span>
            </button>
          )}
          {!visibleProducts.length && <div className="empty-state"><Search size={28} /><h3>No exact match yet</h3><p>Try a broader need or ask Niyam to help.</p></div>}
        </section>

        <section className="how-section" id="trust">
          <div className="section-heading centered"><span className="kicker">HOW IT STAYS SAFE</span><h2>Helpful automation. Human authority.</h2></div>
          <div className="steps">
            <article><span>01</span><h3>You set the rules</h3><p>Share your goal, budget and preferences. Niyam stays inside them.</p></article>
            <article><span>02</span><h3>Niyam explains</h3><p>Every product and add-on includes a reason, price and trade-off.</p></article>
            <article><span>03</span><h3>You approve</h3><p>The exact cart is locked for review before Razorpay test checkout begins.</p></article>
          </div>
        </section>
      </main>

      <button className="agent-fab" onClick={() => setAgentOpen(!agentOpen)} aria-label="Open Niyam assistant">
        <Sparkles size={20} /><span>Ask Niyam</span>
      </button>

      {agentOpen && (
        <aside className="agent-panel" id="agent" aria-label="Niyam AI assistant">
          <div className="panel-header">
            <div className="agent-identity"><span><Bot size={20} /></span><div><b>Niyam</b><small><i /> {agentLoading ? "Working within your rules" : "Ready to help"}</small></div></div>
            <button onClick={() => setAgentOpen(false)} aria-label="Close assistant"><X size={19} /></button>
          </div>
          <div className="agent-body">
            <div className="assistant-message"><b>Hi, I’m Niyam.</b><p>Tell me what you’re shopping for, your budget and what matters most. I’ll explain every choice.</p></div>
            {!agentAnswer && !agentLoading && <div className="quick-prompts">{suggestions.map((item) => <button onClick={() => void askAgent(item)} key={item}>{item}<ArrowRight size={14} /></button>)}</div>}
            {agentLoading && <div className="agent-state" role="status" aria-live="polite"><LoaderCircle className="spin" size={18} /><div><b>Checking the live catalogue</b><small>Niyam may use bounded tools, but cannot order or pay.</small></div></div>}
            {agentError && <div className="agent-state error-state" role="alert"><CircleX size={18} /><div><b>Request not completed</b><small>{agentError}</small></div></div>}
            {agentAnswer && (
              <>
                <div className="user-message">{agentQuery}</div>
                {agentRun?.status === "degraded" && <div className="agent-state degraded-state" role="status"><ShieldCheck size={18} /><div><b>Safe fallback used</b><small>The AI provider was unavailable. Results below came from deterministic catalogue search.</small></div></div>}
                <div className="assistant-message"><span className="reason-label"><Sparkles size={13} /> GROUNDED RESPONSE</span><p>{agentAnswer}</p>{agentRun?.proposed_cart_id && <button className="inline-action" onClick={() => void reviewAgentCart()}>Review proposed cart <ArrowRight size={15} /></button>}</div>
                {!!recommendations.length && <div className="grounded-results" aria-label="Products returned by catalogue tools"><b>Catalogue evidence</b>{recommendations.map((item) => <div key={item.product_id}><span><strong>{item.name}</strong><small>{item.product_id} · {item.stock} in stock</small></span><b>{formatMoney(item.price_paise)}</b></div>)}</div>}
                {!!visibleAgentEvents.length && <details className="audit-timeline" open><summary><span><Wrench size={14} /> Tool activity & audit</span>{verifiedAudit?.valid ? <em className="verified"><CircleCheckBig size={13} /> Verified</em> : <em className="unverified"><CircleX size={13} /> Unverified</em>}</summary><ol>{visibleAgentEvents.map((event) => <li key={event.sequence}><span>{event.sequence}</span><div><b>{event.tool_name || event.event_type.replaceAll("_", " ")}</b><small>{event.event_type === "tool_call" ? "Bounded tool requested" : event.event_type === "tool_result" ? "Typed result recorded" : event.event_type === "policy_decision" ? String(event.payload.rule_id || "Policy evaluated") : event.event_type === "final_answer" ? "Response completed" : "Event recorded"}</small></div></li>)}</ol>{verifiedAudit && <code title={verifiedAudit.root_hash}>Root {verifiedAudit.root_hash}</code>}<p>Only actions and typed results are shown. Hidden model reasoning is never exposed.</p></details>}
              </>
            )}
          </div>
          <div className="agent-input">
            <input value={agentQuery} onChange={(event) => setAgentQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && !agentLoading && void askAgent()} placeholder="Describe what you need…" disabled={agentLoading} aria-label="Shopping request" />
            <button onClick={() => void askAgent()} aria-label="Send" disabled={agentLoading || !agentQuery.trim()}>{agentLoading ? <LoaderCircle className="spin" size={18} /> : <ArrowRight size={18} />}</button>
          </div>
          <div className="panel-safety"><ShieldCheck size={13} /> Niyam cannot purchase without your approval</div>
        </aside>
      )}

      {cartOpen && <CartDrawer key={cartLines.map(({ product, quantity }) => `${product.id}:${quantity}`).join("|")} lines={cartLines} subtotal={subtotal} updateCart={updateCart} close={() => setCartOpen(false)} />}
    </div>
  );
}

function ProductCard({ product, quantity, updateCart }: { product: Product; quantity: number; updateCart: (id: string, delta: number) => void }) {
  return (
    <article className="product-card">
      <div className="product-visual" style={{ background: product.accent }}>
        {product.badge && <span className="product-badge">{product.badge}</span>}
        <img className="product-image" src={product.image} alt={product.name} loading="lazy" />
        <button className="view-button">Quick view</button>
      </div>
      <div className="product-info">
        <span className="product-category">{product.category}</span>
        <h3>{product.name}</h3>
        <p>{product.description}</p>
        <div className="rating"><Star size={14} fill="currentColor" /> <b>{product.rating}</b><span>({product.reviews})</span></div>
        <div className="product-bottom">
          <div className="price"><strong>{formatMoney(product.pricePaise)}</strong>{product.originalPricePaise && <del>{formatMoney(product.originalPricePaise)}</del>}</div>
          {quantity ? (
            <div className="quantity-control"><button onClick={() => updateCart(product.id, -1)}><Minus size={15} /></button><b>{quantity}</b><button onClick={() => updateCart(product.id, 1)}><Plus size={15} /></button></div>
          ) : (
            <button className="add-button" onClick={() => updateCart(product.id, 1)}><Plus size={17} /> Add</button>
          )}
        </div>
      </div>
    </article>
  );
}

function CartDrawer({ lines, subtotal, updateCart, close }: { lines: { product: Product; quantity: number }[]; subtotal: number; updateCart: (id: string, delta: number) => void; close: () => void }) {
  const [approval, setApproval] = useState<ApprovalCart | null>(null);
  const [checkoutState, setCheckoutState] = useState<
    "idle" | "locking" | "ready" | "opening" | "paid"
  >("idle");
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [whatsappOptIn, setWhatsappOptIn] = useState(false);
  const [whatsappState, setWhatsappState] = useState<WhatsAppHandoff | null>(null);
  const [whatsappLoading, setWhatsappLoading] = useState(false);
  const [whatsappError, setWhatsappError] = useState<string | null>(null);
  const lockCart = async () => {
    setCheckoutState("locking");
    setCheckoutError(null);
    try {
      const frozen = await prepareCartForApproval(
        lines.map(({ product, quantity }) => ({ productId: product.id, quantity })),
      );
      setApproval(frozen);
      setCheckoutState("ready");
    } catch (error) {
      setCheckoutState("idle");
      setCheckoutError(error instanceof Error ? error.message : "The cart could not be locked.");
    }
  };

  const approveAndPay = async () => {
    if (!approval) return;
    setCheckoutState("opening");
    setCheckoutError(null);
    try {
      const verified = await approveAndOpenCheckout(approval);
      setCheckoutState("paid");
      if (whatsappOptIn) {
        try {
          const confirmation = await prepareWhatsAppConfirmation(verified.orderId);
          setWhatsappState(confirmation);
        } catch (error) {
          setWhatsappError(
            error instanceof Error ? error.message : "Confirmation handoff is unavailable.",
          );
        }
      }
    } catch (error) {
      setCheckoutState("ready");
      setCheckoutError(error instanceof Error ? error.message : "Payment was not verified.");
    }
  };

  const prepareWhatsApp = async () => {
    if (!approval || !whatsappOptIn) return;
    setWhatsappLoading(true);
    setWhatsappError(null);
    try {
      setWhatsappState(await prepareWhatsAppReview(approval.id, approval.cart_hash));
    } catch (error) {
      setWhatsappError(error instanceof Error ? error.message : "Handoff could not be prepared.");
    } finally {
      setWhatsappLoading(false);
    }
  };

  const copyHandoff = async () => {
    if (whatsappState?.share_text) await navigator.clipboard.writeText(whatsappState.share_text);
  };

  return (
    <div className="drawer-layer">
      <button className="drawer-backdrop" onClick={close} aria-label="Close cart" />
      <aside className="cart-drawer">
        <div className="drawer-header"><div><span className="kicker">YOUR SELECTION</span><h2>Review cart</h2></div><button onClick={close}><X size={21} /></button></div>
        <div className="cart-lines">
          {!lines.length && <div className="empty-cart"><ShoppingBag size={32} /><h3>Your cart is empty</h3><p>Add a product or ask Niyam to build a cart for you.</p></div>}
          {lines.map(({ product, quantity }) => (
            <div className="cart-line" key={product.id}>
              <span className="line-visual" style={{ background: product.accent }}><img src={product.image} alt="" /></span>
              <div className="line-copy"><b>{product.name}</b><small>{formatMoney(product.pricePaise)} each</small><div className="quantity-control"><button onClick={() => updateCart(product.id, -1)}>{quantity === 1 ? <Trash2 size={14} /> : <Minus size={14} />}</button><b>{quantity}</b><button onClick={() => updateCart(product.id, 1)}><Plus size={14} /></button></div></div>
              <strong>{formatMoney(product.pricePaise * quantity)}</strong>
            </div>
          ))}
        </div>
        {!!lines.length && <div className="cart-summary">
          <div><span>Subtotal</span><b>{formatMoney(subtotal)}</b></div>
          <div><span>Delivery</span><b className="free">Free</b></div>
          <div className="total-line"><span>Total</span><strong>{formatMoney(subtotal)}</strong></div>
          <div className="approval-box"><ShieldCheck size={19} /><p><b>You remain in control</b><small>We’ll lock and show the exact cart again before opening Razorpay test checkout.</small></p></div>
          {approval && checkoutState !== "paid" && (
            <div className="exact-approval">
              <span>Exact cart awaiting your approval</span>
              <b>{formatMoney(approval.total_paise)}</b>
              <code title={approval.cart_hash}>{approval.cart_hash}</code>
              <small>
                Locked until {new Date(
                  approval.expires_at.endsWith("Z")
                    ? approval.expires_at
                    : `${approval.expires_at}Z`,
                ).toLocaleTimeString()}
              </small>
            </div>
          )}
          {approval && (
            <div className="whatsapp-box">
              <label><input type="checkbox" checked={whatsappOptIn} onChange={(event) => { setWhatsappOptIn(event.target.checked); setWhatsappState(null); }} /><span><b><MessageCircle size={15} /> WhatsApp handoff</b><small>Optional. Prepares a review-only message; it never approves or pays.</small></span></label>
              {whatsappOptIn && !whatsappState && <button onClick={prepareWhatsApp} disabled={whatsappLoading}>{whatsappLoading ? "Preparing…" : "Prepare review message"}</button>}
              {whatsappState && <div className="handoff-result" role="status"><small>{whatsappState.message}</small>{whatsappState.share_text && <button onClick={copyHandoff}><Copy size={13} /> Copy message</button>}</div>}
              {whatsappError && <small className="checkout-error" role="alert">{whatsappError}</small>}
            </div>
          )}
          {checkoutState === "paid" ? (
            <div className="payment-success" role="status" aria-live="polite"><Check size={18} /><b>Payment verified by NiyamCart</b></div>
          ) : approval ? (
            <button className="checkout-button" onClick={approveAndPay} disabled={checkoutState === "opening"}>
              {checkoutState === "opening" ? "Opening secure checkout…" : "Approve exact cart & pay"}
              <ArrowRight size={18} />
            </button>
          ) : (
            <button className="checkout-button" onClick={lockCart} disabled={checkoutState === "locking"}>
              {checkoutState === "locking" ? "Locking authoritative prices…" : "Continue to approval"}
              <ArrowRight size={18} />
            </button>
          )}
          {checkoutError && <p className="checkout-error" role="alert">{checkoutError}</p>}
          <small className="test-mode" aria-live="polite">Razorpay test mode · No real money charged</small>
        </div>}
      </aside>
    </div>
  );
}
