"use client";

import {
  ArrowRight,
  Bot,
  Check,
  ChevronDown,
  CircleHelp,
  Minus,
  Plus,
  Search,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Star,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import { formatMoney, products, type Product } from "@/lib/catalog";

type Cart = Record<string, number>;

const suggestions = [
  "Build a work-from-home setup under ₹10,000",
  "Find travel-friendly audio",
  "Compare the best workspace products",
];

export function NiyamCartApp() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [cart, setCart] = useState<Cart>({});
  const [cartOpen, setCartOpen] = useState(false);
  const [agentOpen, setAgentOpen] = useState(true);
  const [agentQuery, setAgentQuery] = useState("");
  const [agentAnswer, setAgentAnswer] = useState<string | null>(null);

  const categories = ["All", ...Array.from(new Set(products.map((item) => item.category)))];
  const visibleProducts = products.filter((item) => {
    const matchesCategory = category === "All" || item.category === category;
    const haystack = `${item.name} ${item.description} ${item.tags.join(" ")}`.toLowerCase();
    return matchesCategory && haystack.includes(query.toLowerCase());
  });

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

  const askAgent = (prompt = agentQuery) => {
    if (!prompt.trim()) return;
    setAgentQuery(prompt);
    setAgentAnswer(
      "I found a balanced setup under your ₹10,000 limit: Orbit ANC Headphones and Loop Laptop Stand. Together they cost ₹8,098, leaving ₹1,902 in your budget. I chose them for work calls, comfort and strong buyer ratings.",
    );
  };

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
            <h2>Your focused work setup</h2>
            <p>Two highly rated products that fit your needs and stay below ₹10,000.</p>
            <div className="bundle-items">
              <div><span>🎧</span><p><b>Orbit ANC</b><small>Clear calls</small></p><strong>₹6,499</strong></div>
              <div><span>💻</span><p><b>Loop Stand</b><small>Better posture</small></p><strong>₹1,599</strong></div>
            </div>
            <div className="bundle-total"><span>Total</span><b>₹8,098</b></div>
            <button onClick={() => { setCart({ "orbit-headphones": 1, "loop-stand": 1 }); setCartOpen(true); }}>
              Review this cart <ArrowRight size={17} />
            </button>
            <small className="approval-note"><ShieldCheck size={14} /> Nothing is purchased until you approve</small>
          </div>
        </section>

        <section className="shop-section" id="shop">
          <div className="section-heading">
            <div><span className="kicker">CURATED FOR REAL LIFE</span><h2>Products worth choosing</h2></div>
            <p>Clear details, honest prices and recommendations you can understand.</p>
          </div>

          <div className="shop-tools">
            <label className="search-box">
              <Search size={19} />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search products or needs" />
              {query && <button onClick={() => setQuery("")} aria-label="Clear search"><X size={16} /></button>}
            </label>
            <div className="category-tabs">
              {categories.map((item) => (
                <button className={category === item ? "selected" : ""} onClick={() => setCategory(item)} key={item}>{item}</button>
              ))}
            </div>
            <button className="sort-button">Recommended <ChevronDown size={16} /></button>
          </div>

          <div className="product-grid">
            {visibleProducts.map((product) => (
              <ProductCard product={product} quantity={cart[product.id] || 0} updateCart={updateCart} key={product.id} />
            ))}
          </div>
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
            <div className="agent-identity"><span><Bot size={20} /></span><div><b>Niyam</b><small><i /> Ready to help</small></div></div>
            <button onClick={() => setAgentOpen(false)} aria-label="Close assistant"><X size={19} /></button>
          </div>
          <div className="agent-body">
            <div className="assistant-message"><b>Hi, I’m Niyam.</b><p>Tell me what you’re shopping for, your budget and what matters most. I’ll explain every choice.</p></div>
            {!agentAnswer && <div className="quick-prompts">{suggestions.map((item) => <button onClick={() => askAgent(item)} key={item}>{item}<ArrowRight size={14} /></button>)}</div>}
            {agentAnswer && (
              <>
                <div className="user-message">{agentQuery}</div>
                <div className="assistant-message"><span className="reason-label"><Sparkles size={13} /> EXPLAINED RECOMMENDATION</span><p>{agentAnswer}</p><button className="inline-action" onClick={() => { setCart({ "orbit-headphones": 1, "loop-stand": 1 }); setCartOpen(true); }}>Review proposed cart <ArrowRight size={15} /></button></div>
              </>
            )}
          </div>
          <div className="agent-input">
            <input value={agentQuery} onChange={(event) => setAgentQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && askAgent()} placeholder="Describe what you need…" />
            <button onClick={() => askAgent()} aria-label="Send"><ArrowRight size={18} /></button>
          </div>
          <div className="panel-safety"><ShieldCheck size={13} /> Niyam cannot purchase without your approval</div>
        </aside>
      )}

      {cartOpen && <CartDrawer lines={cartLines} subtotal={subtotal} updateCart={updateCart} close={() => setCartOpen(false)} />}
    </div>
  );
}

function ProductCard({ product, quantity, updateCart }: { product: Product; quantity: number; updateCart: (id: string, delta: number) => void }) {
  return (
    <article className="product-card">
      <div className="product-visual" style={{ background: product.accent }}>
        {product.badge && <span className="product-badge">{product.badge}</span>}
        <span className="product-emoji">{product.emoji}</span>
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
  return (
    <div className="drawer-layer">
      <button className="drawer-backdrop" onClick={close} aria-label="Close cart" />
      <aside className="cart-drawer">
        <div className="drawer-header"><div><span className="kicker">YOUR SELECTION</span><h2>Review cart</h2></div><button onClick={close}><X size={21} /></button></div>
        <div className="cart-lines">
          {!lines.length && <div className="empty-cart"><ShoppingBag size={32} /><h3>Your cart is empty</h3><p>Add a product or ask Niyam to build a cart for you.</p></div>}
          {lines.map(({ product, quantity }) => (
            <div className="cart-line" key={product.id}>
              <span className="line-visual" style={{ background: product.accent }}>{product.emoji}</span>
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
          <button className="checkout-button">Continue to approval <ArrowRight size={18} /></button>
          <small className="test-mode">Razorpay test mode · No real money charged</small>
        </div>}
      </aside>
    </div>
  );
}
