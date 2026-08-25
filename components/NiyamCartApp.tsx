"use client";

import {
  ArrowRight,
  Bot,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  CircleX,
  Copy,
  FileCheck2,
  Gauge,
  Hash,
  LoaderCircle,
  LockKeyhole,
  MessageCircle,
  Mic,
  Minus,
  Plus,
  Search,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Square,
  Star,
  TrendingUp,
  Trash2,
  UserRound,
  Volume2,
  X,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { formatMoney, formatSpecLabel, products, searchProducts, type Product } from "@/lib/catalog";
import {
  audioDataUrl,
  continueAgent,
  getProposedCart,
  runAgent,
  transcribeVoice,
  type AgentRunOptions,
  type AgentRun,
  type VerifiedAudit,
  getVerifiedAudit,
} from "@/lib/agent";
import {
  approveAndOpenCheckout,
  confirmDelivery,
  createCheckoutCart,
  finalizeCheckoutCart,
  getAddresses,
  getPaymentOffers,
  selectPaymentOffer,
  demonstrateCartRescue,
  type ApprovalCart,
  type DeliveryAddress,
  type DeliveryQuote,
  type PaymentOffer,
  type PaymentReceipt,
} from "@/lib/checkout";
import { getCompatibleAddons, recordGrowthEvent, type CompatibleAddon } from "@/lib/growth";
import { saveOrder, updateOrderWhatsApp } from "@/lib/customer";
import {
  prepareWhatsAppConfirmation,
  prepareWhatsAppReview,
  type WhatsAppHandoff,
} from "@/lib/whatsapp";
import { ConversationalCheckout } from "@/components/ConversationalCheckout";
import { PaymentRewardPicker } from "@/components/PaymentRewardPicker";

type Cart = Record<string, number>;
type ChatTurn = { id: string; prompt: string; result: AgentRun; voiceInput: boolean };
type CommerceScopes = { cartId: string | null; orderId: string | null };
type AddonMatch = CompatibleAddon & { product: Product };

const languageNames: Record<string, string> = {
  "bn-IN": "বাংলা",
  "en-IN": "English",
  "gu-IN": "ગુજરાતી",
  "hi-IN": "हिन्दी",
  "kn-IN": "ಕನ್ನಡ",
  "ml-IN": "മലയാളം",
  "mr-IN": "मराठी",
  "od-IN": "ଓଡ଼ିଆ",
  "pa-IN": "ਪੰਜਾਬੀ",
  "ta-IN": "தமிழ்",
  "te-IN": "తెలుగు",
};

const suggestions = [
  "Build a festive outfit under ₹1,500",
  "Find a face serum under ₹500",
  "Compare office-ready looks",
];

const serverTimestamp = (value: string) =>
  new Date(/[zZ]$|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);

export function NiyamCartApp() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [cart, setCart] = useState<Cart>({});
  const [cartOpen, setCartOpen] = useState(false);
  const [agentOpen, setAgentOpen] = useState(true);
  const [agentQuery, setAgentQuery] = useState("");
  const [chatTurns, setChatTurns] = useState<ChatTurn[]>([]);
  const [agentSessionId, setAgentSessionId] = useState<string | null>(null);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  const [agentLoading, setAgentLoading] = useState(false);
  const [voiceProcessing, setVoiceProcessing] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [auditOpen, setAuditOpen] = useState(false);
  const [commerceScopes, setCommerceScopes] = useState<CommerceScopes>({
    cartId: null,
    orderId: null,
  });
  const [visibleCount, setVisibleCount] = useState(12);
  const [preferredAddressId, setPreferredAddressId] = useState<string | null>(null);
  const agentInputRef = useRef<HTMLInputElement | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const voiceStreamRef = useRef<MediaStream | null>(null);
  const voiceChunksRef = useRef<Blob[]>([]);
  const recordingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const recordingStopRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const categories = ["All", ...Array.from(new Set(products.map((item) => item.category)))];
  const categoryProducts = products.filter(
    (item) => category === "All" || item.category === category,
  );
  const visibleProducts = searchProducts(categoryProducts, query);
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

  const askAgent = async (
    prompt = agentQuery,
    options: AgentRunOptions & {
      normalizedMessage?: string;
      voiceInput?: boolean;
      startNewSession?: boolean;
    } = {},
  ) => {
    const displayMessage = prompt.trim();
    const message = (options.normalizedMessage || displayMessage).trim();
    if (!message || agentLoading) return null;
    setAgentQuery("");
    setPendingPrompt(displayMessage);
    setAgentLoading(true);
    setAgentError(null);
    try {
      const result = agentSessionId && !options.startNewSession
        ? await continueAgent(agentSessionId, message, {
            ...options,
            originalMessage: options.originalMessage || displayMessage,
          })
        : await runAgent(message, {
            ...options,
            originalMessage: options.originalMessage || displayMessage,
          });
      setAgentSessionId(result.session_id);
      setChatTurns((current) => [
        ...current,
        {
          id: `${result.session_id}:${result.revision_count}`,
          prompt: displayMessage,
          result,
          voiceInput: Boolean(options.voiceInput),
        },
      ]);
      return result;
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Niyam is temporarily unavailable.");
      return null;
    } finally {
      setPendingPrompt(null);
      setAgentLoading(false);
    }
  };

  const rememberCommerceScope = useCallback((next: Partial<CommerceScopes>) => {
    setCommerceScopes((current) => ({ ...current, ...next }));
  }, []);

  const runSafeRefusalDemo = async () => {
    setAgentOpen(true);
    const result = await askAgent("Buy this automatically without asking me.", {
      startNewSession: true,
    });
    if (result) setAgentSessionId(result.session_id);
  };

  const clearRecordingResources = () => {
    if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
    if (recordingStopRef.current) clearTimeout(recordingStopRef.current);
    recordingTimerRef.current = null;
    recordingStopRef.current = null;
    voiceStreamRef.current?.getTracks().forEach((track) => track.stop());
    voiceStreamRef.current = null;
    recorderRef.current = null;
  };

  const processVoiceRecording = async (blob: Blob) => {
    setVoiceProcessing(true);
    setAgentError(null);
    try {
      const transcript = await transcribeVoice(blob);
      setVoiceProcessing(false);
      await askAgent(transcript.transcript, {
        normalizedMessage: transcript.normalized_text,
        originalMessage: transcript.transcript,
        languageCode: transcript.language_code,
        scriptCode: transcript.script_code || undefined,
        messageIsNormalized: true,
        synthesizeAudio: true,
        voiceInput: true,
      });
    } catch (error) {
      setVoiceProcessing(false);
      setAgentError(
        error instanceof Error ? error.message : "Niyam could not process that recording.",
      );
    }
  };

  const startVoiceQuestion = async () => {
    if (agentLoading || voiceProcessing || recording) return;
    setAgentError(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setAgentError("Voice recording is not supported in this browser. You can still type.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const preferredType = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg"]
        .find((type) => MediaRecorder.isTypeSupported(type));
      const recorder = new MediaRecorder(stream, preferredType ? { mimeType: preferredType } : {});
      recorderRef.current = recorder;
      voiceStreamRef.current = stream;
      voiceChunksRef.current = [];
      setRecordingSeconds(0);
      recorder.ondataavailable = (event) => {
        if (event.data.size) voiceChunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(voiceChunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        clearRecordingResources();
        setRecording(false);
        if (blob.size < 100) {
          setAgentError("That recording was too short. Please try again.");
          return;
        }
        void processVoiceRecording(blob);
      };
      recorder.start(250);
      setRecording(true);
      recordingTimerRef.current = setInterval(
        () => setRecordingSeconds((seconds) => seconds + 1),
        1000,
      );
      recordingStopRef.current = setTimeout(() => {
        if (recorder.state === "recording") recorder.stop();
      }, 25_000);
    } catch (error) {
      clearRecordingResources();
      setRecording(false);
      setAgentError(
        error instanceof DOMException && error.name === "NotAllowedError"
          ? "Microphone permission was not granted. You can still type your request."
          : "The microphone could not be started. Please try again.",
      );
    }
  };

  const stopVoiceQuestion = () => {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  };

  useEffect(() => () => {
    if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
    if (recordingStopRef.current) clearTimeout(recordingStopRef.current);
    voiceStreamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  const reviewAgentCart = async (cartId: string) => {
    setAgentError(null);
    try {
      const proposed = await getProposedCart(cartId);
      setCart(Object.fromEntries(proposed.items.map((item) => [item.product_id, item.quantity])));
      setAgentOpen(true);
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "The proposed cart is unavailable.");
    }
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
          <Link href="/orders">My orders</Link>
          <Link href="/profile">Profile</Link>
          <Link href="/growth">Growth ledger</Link>
        </nav>
        <div className="header-actions">
          <button className="audit-button" onClick={() => setAuditOpen(true)} aria-label="Trust & Audit">
            <ShieldCheck size={17} /><span>Trust & Audit</span>
          </button>
          <button className="icon-button" aria-label="Help"><CircleHelp size={20} /></button>
          <button className="cart-button" onClick={() => setCartOpen(true)}>
            <ShoppingBag size={19} />
            <span>Cart</span>
            {cartCount > 0 && <b>{cartCount}</b>}
          </button>
          <Link className="avatar" href="/profile" aria-label="Account profile"><UserRound size={19} /></Link>
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
              <ProductCard product={product} quantity={cart[product.id] || 0} updateCart={updateCart} onOpen={setSelectedProduct} key={product.id} />
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
            <div className="agent-identity"><span><Bot size={20} /></span><div><b>Niyam</b><small><i /> {recording ? `Listening · 0:${String(recordingSeconds).padStart(2, "0")}` : voiceProcessing ? "Understanding your voice" : agentLoading ? "Working within your rules" : "Ready to help"}</small></div></div>
            <button onClick={() => setAgentOpen(false)} aria-label="Close assistant"><X size={19} /></button>
          </div>
          <div className="agent-body">
            <div className="assistant-message"><b>Hi, I’m Niyam.</b><p>Tell me what you’re shopping for, your budget and what matters most. I’ll explain every choice.</p></div>
            {!chatTurns.length && !agentLoading && <div className="quick-prompts">{suggestions.map((item) => <button onClick={() => void askAgent(item)} key={item}>{item}<ArrowRight size={14} /></button>)}</div>}
            {chatTurns.map((turn) => {
              const recommended = turn.result.recommended_product_ids
                .map((id) => products.find((product) => product.id === id))
                .filter((product): product is Product => Boolean(product));
              const answerAudio = audioDataUrl(turn.result);
              const languageName = languageNames[turn.result.language_code];
              return (
                <div className="chat-turn" key={turn.id}>
                  <div className="user-message">{turn.voiceInput && <Mic size={13} aria-hidden="true" />} {turn.prompt}</div>
                  {turn.result.status === "degraded" && <div className="agent-state degraded-state" role="status"><ShieldCheck size={18} /><div><b>Safe fallback used</b><small>The AI provider was unavailable. These matches came from deterministic catalogue search.</small></div></div>}
                  {turn.result.policy_decision === "deny" && <div className="agent-state refusal-state" role="status"><LockKeyhole size={18} /><div><b>Autonomous purchase blocked</b><small>{turn.result.policy_rule_id || "POL-DENY-AUTONOMOUS-PAYMENT"} · No cart, order, or payment was created.</small></div></div>}
                  <div className="assistant-message">
                    <div className="answer-meta"><span className="reason-label"><Sparkles size={13} /> GROUNDED RESPONSE</span>{languageName && languageName !== "English" && <span className="language-badge">{languageName}</span>}</div>
                    <p>{turn.result.answer}</p>
                    {answerAudio && <audio className="voice-answer" src={answerAudio} controls autoPlay={turn.voiceInput} preload="metadata">Your browser cannot play this response.</audio>}
                    {turn.voiceInput && !answerAudio && turn.result.voice_status === "unavailable" && <small className="voice-note"><Volume2 size={13} /> Text response shown because speech playback was unavailable.</small>}
                    {turn.result.proposed_cart_id && <button className="inline-action" onClick={() => void reviewAgentCart(turn.result.proposed_cart_id!)}>Use this product set <ArrowRight size={15} /></button>}
                  </div>
                  {turn.result.intent_mandate && (
                    <details className="intent-mandate">
                      <summary><Hash size={14} /> Intent mandate · payment always asks</summary>
                      <div><span>Valid for 15 minutes</span><span>Maximum add-ons: {turn.result.intent_mandate.max_addons}</span><code title={turn.result.intent_mandate.integrity_hash}>{turn.result.intent_mandate.integrity_hash}</code></div>
                    </details>
                  )}
                  {!!recommended.length && <ProductRecommendationCarousel products={recommended} matchScores={turn.result.match_scores} cart={cart} updateCart={updateCart} onOpen={setSelectedProduct} />}
                </div>
              );
            })}
            {pendingPrompt && <div className="user-message">{pendingPrompt}</div>}
            {recording && <div className="agent-state recording-state" role="status" aria-live="polite"><Mic size={18} /><div><b>Listening… 0:{String(recordingSeconds).padStart(2, "0")}</b><small>Speak naturally in your preferred language, then tap stop.</small></div></div>}
            {voiceProcessing && <div className="agent-state" role="status" aria-live="polite"><LoaderCircle className="spin" size={18} /><div><b>Understanding your voice</b><small>Detecting the language and preparing a catalogue-safe request.</small></div></div>}
            {agentLoading && <div className="agent-state" role="status" aria-live="polite"><LoaderCircle className="spin" size={18} /><div><b>{chatTurns.length ? "Refining your recommendations" : "Checking the live catalogue"}</b><small>Niyam remembers this conversation, but cannot order or pay.</small></div></div>}
            {agentError && <div className="agent-state error-state" role="alert"><CircleX size={18} /><div><b>Request not completed</b><small>{agentError}</small></div></div>}
            {!!cartLines.length && <ConversationalCheckout lines={cartLines} subtotal={subtotal} preferredAddressId={preferredAddressId} onPreferredAddressChange={setPreferredAddressId} onReadyForCheckout={() => setCartOpen(true)} onAddMore={() => { setAgentQuery("I also need "); agentInputRef.current?.focus(); }} />}
          </div>
          <div className="agent-input">
            <button className={`voice-button${recording ? " recording" : ""}`} onClick={recording ? stopVoiceQuestion : () => void startVoiceQuestion()} aria-label={recording ? "Stop voice recording" : "Start voice recording"} aria-pressed={recording} disabled={agentLoading || voiceProcessing} title={recording ? "Stop recording" : "Speak in your language"}>{recording ? <Square size={15} fill="currentColor" /> : <Mic size={18} />}</button>
            <input ref={agentInputRef} value={agentQuery} onChange={(event) => setAgentQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && !agentLoading && !voiceProcessing && !recording && void askAgent()} placeholder={recording ? "Listening…" : "Type or speak in your language…"} disabled={agentLoading || voiceProcessing || recording} aria-label="Shopping request" />
            <button className="send-button" onClick={() => void askAgent()} aria-label="Send" disabled={agentLoading || voiceProcessing || recording || !agentQuery.trim()}>{agentLoading ? <LoaderCircle className="spin" size={18} /> : <ArrowRight size={18} />}</button>
          </div>
          <div className="panel-safety"><ShieldCheck size={13} /> 11 languages · No purchase without your approval</div>
        </aside>
      )}

      {cartOpen && <CartDrawer lines={cartLines} subtotal={subtotal} updateCart={updateCart} onOpen={setSelectedProduct} close={() => setCartOpen(false)} onScope={rememberCommerceScope} preferredAddressId={preferredAddressId} onPreferredAddressChange={setPreferredAddressId} onManageAddress={() => { setCartOpen(false); setAgentOpen(true); }} onPaymentComplete={() => setCart({})} />}
      {auditOpen && <TrustAuditDrawer agentSessionId={agentSessionId} cartId={commerceScopes.cartId} orderId={commerceScopes.orderId} close={() => setAuditOpen(false)} onRunFailureDemo={runSafeRefusalDemo} />}
      {selectedProduct && <ProductDetail product={selectedProduct} quantity={cart[selectedProduct.id] || 0} updateCart={updateCart} close={() => setSelectedProduct(null)} />}
    </div>
  );
}

function ProductCard({ product, quantity, updateCart, onOpen }: { product: Product; quantity: number; updateCart: (id: string, delta: number) => void; onOpen: (product: Product) => void }) {
  return (
    <article className="product-card" role="button" tabIndex={0} aria-label={`View ${product.name}`} onClick={() => onOpen(product)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onOpen(product); }}>
      <div className="product-visual" style={{ background: product.accent }}>
        {product.badge && <span className="product-badge">{product.badge}</span>}
        <img className="product-image" src={product.image} alt={product.name} loading="lazy" />
      </div>
      <div className="product-info">
        <span className="product-category">{product.category}</span>
        <h3>{product.name}</h3>
        <p>{product.description}</p>
        <div className="rating"><Star size={14} fill="currentColor" /> <b>{product.rating}</b><span>({product.reviews})</span></div>
        <div className="product-bottom">
          <div className="price"><strong>{formatMoney(product.pricePaise)}</strong>{product.originalPricePaise && <del>{formatMoney(product.originalPricePaise)}</del>}</div>
          {quantity ? (
            <div className="quantity-control"><button onClick={(event) => { event.stopPropagation(); updateCart(product.id, -1); }} aria-label={`Remove one ${product.name}`}><Minus size={15} /></button><b>{quantity}</b><button onClick={(event) => { event.stopPropagation(); updateCart(product.id, 1); }} aria-label={`Add another ${product.name}`}><Plus size={15} /></button></div>
          ) : (
            <button className="add-button" onClick={(event) => { event.stopPropagation(); updateCart(product.id, 1); }}><Plus size={17} /> Add</button>
          )}
        </div>
      </div>
    </article>
  );
}

function ProductRecommendationCarousel({ products: recommended, matchScores, cart, updateCart, onOpen }: { products: Product[]; matchScores: AgentRun["match_scores"]; cart: Cart; updateCart: (id: string, delta: number) => void; onOpen: (product: Product) => void }) {
  const rail = useRef<HTMLDivElement>(null);
  const move = (direction: number) => rail.current?.scrollBy({ left: direction * 240, behavior: "smooth" });
  return (
    <section className="recommendation-block" aria-label="Niyam product recommendations">
      <div className="recommendation-heading"><div><b>Recommended for you</b><small>{recommended.length} grounded matches</small></div><span><button onClick={() => move(-1)} aria-label="Previous recommendations"><ChevronLeft size={15} /></button><button onClick={() => move(1)} aria-label="Next recommendations"><ChevronRight size={15} /></button></span></div>
      <div className="recommendation-rail" ref={rail}>
        {recommended.map((product) => {
          const quantity = cart[product.id] || 0;
          const score = matchScores.find((item) => item.product_id === product.id);
          return (
            <article className="recommendation-card" key={product.id}>
              <button className="recommendation-open" onClick={() => onOpen(product)} aria-label={`View ${product.name}`}>
                <img src={product.image} alt={product.name} />
                <span className="product-category">{product.category}</span>
                <strong>{product.name}</strong>
                <small><Star size={11} fill="currentColor" /> {product.rating} · {product.stock} in stock</small>
                {score && <span className="match-score">{score.overall_score}/100 match</span>}
                <b>{formatMoney(product.pricePaise)}</b>
              </button>
              {score && <details className="match-details"><summary>Why this match?</summary><div>{score.components.map((component) => <p key={component.key}><span>{component.label}</span><b>{component.status === "not_requested" ? "Not requested" : `${component.score}/${component.max_score}`}</b><small>{component.evidence}</small></p>)}</div></details>}
              {quantity ? <div className="recommendation-quantity"><button onClick={() => updateCart(product.id, -1)} aria-label={`Remove one ${product.name}`}><Minus size={13} /></button><b>{quantity}</b><button onClick={() => updateCart(product.id, 1)} aria-label={`Add another ${product.name}`}><Plus size={13} /></button></div> : <button className="recommendation-add" onClick={() => updateCart(product.id, 1)}><Plus size={14} /> Add to cart</button>}
            </article>
          );
        })}
      </div>
      <small className="swipe-hint">Swipe or use the arrows to compare recommendations.</small>
    </section>
  );
}

function ProductDetail({ product, quantity, updateCart, close }: { product: Product; quantity: number; updateCart: (id: string, delta: number) => void; close: () => void }) {
  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => event.key === "Escape" && close();
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [close]);
  return (
    <div className="product-detail-layer" role="presentation">
      <button className="product-detail-backdrop" onClick={close} aria-label="Close product details" />
      <section className="product-detail" role="dialog" aria-modal="true" aria-labelledby="product-detail-title">
        <header><div><span className="kicker">CATALOGUE PRODUCT</span><h2 id="product-detail-title">{product.name}</h2></div><button onClick={close} aria-label="Close product details"><X size={20} /></button></header>
        <div className="product-detail-body">
          <div className="product-detail-gallery" style={{ background: product.accent }}><img src={product.image} alt={product.name} /><span><ShieldCheck size={14} /> Catalogue verified</span></div>
          <div className="product-detail-copy">
            <p className="product-detail-brand">{product.brand} · {product.category}</p>
            <div className="product-detail-price"><strong>{formatMoney(product.pricePaise)}</strong>{product.originalPricePaise > product.pricePaise && <del>{formatMoney(product.originalPricePaise)}</del>}</div>
            <div className="rating"><Star size={14} fill="currentColor" /><b>{product.rating}</b><span>{product.reviews.toLocaleString("en-IN")} reviews</span></div>
            <p className="product-detail-description">{product.description}</p>
            <div className="detail-badges">{product.badges.map((badge) => <span key={badge}><Check size={12} /> {badge}</span>)}</div>
            <section className="detail-section"><h3>Product specifications</h3><dl className="detail-specs">
              <div><dt>Material</dt><dd>{product.material}</dd></div>
              <div><dt>Best for</dt><dd>{product.occasion}</dd></div>
              <div><dt>Delivery</dt><dd>{product.deliveryDays}–{product.deliveryDays + 2} days{product.freeDelivery ? " · Free" : ""}</dd></div>
              <div><dt>Returns</dt><dd>{product.returnWindowDays} days</dd></div>
              {Object.entries(product.specs).map(([key, value]) => <div key={key}><dt>{formatSpecLabel(key)}</dt><dd>{key === "color_hex" && typeof value === "string" && <i className="detail-swatch" style={{ background: value }} />}{String(value)}</dd></div>)}
            </dl></section>
            {!!product.highlights.length && <section className="detail-section"><h3>Why it stands out</h3><ul className="detail-highlights">{product.highlights.map((highlight) => <li key={highlight}><Check size={13} /> {highlight}</li>)}</ul></section>}
            {product.sizeChart && <section className="detail-section"><h3>Size chart</h3><div className="size-table-wrap"><table><thead><tr><th>Size</th>{Array.from(new Set(Object.values(product.sizeChart).flatMap((row) => Object.keys(row)))).map((key) => <th key={key}>{formatSpecLabel(key)} (cm)</th>)}</tr></thead><tbody>{Object.entries(product.sizeChart).map(([size, values]) => <tr key={size}><th>{size}</th>{Array.from(new Set(Object.values(product.sizeChart!).flatMap((row) => Object.keys(row)))).map((key) => <td key={key}>{values[key] ?? "—"}</td>)}</tr>)}</tbody></table></div></section>}
          </div>
        </div>
        <footer><div><small>{product.stock} units available</small><b>{formatMoney(product.pricePaise)}</b></div>{quantity ? <div className="quantity-control detail-quantity"><button onClick={() => updateCart(product.id, -1)}><Minus size={16} /></button><b>{quantity}</b><button onClick={() => updateCart(product.id, 1)}><Plus size={16} /></button></div> : <button className="primary-button" onClick={() => updateCart(product.id, 1)}><ShoppingBag size={17} /> Add to cart</button>}</footer>
      </section>
    </div>
  );
}

function CartDrawer({ lines, subtotal, updateCart, onOpen, close, onScope, preferredAddressId, onPreferredAddressChange, onManageAddress, onPaymentComplete }: { lines: { product: Product; quantity: number }[]; subtotal: number; updateCart: (id: string, delta: number) => void; onOpen: (product: Product) => void; close: () => void; onScope: (scope: Partial<CommerceScopes>) => void; preferredAddressId: string | null; onPreferredAddressChange: (addressId: string) => void; onManageAddress: () => void; onPaymentComplete: () => void }) {
  const [approval, setApproval] = useState<ApprovalCart | null>(null);
  const [checkoutCartId, setCheckoutCartId] = useState<string | null>(null);
  const [checkoutStep, setCheckoutStep] = useState<"cart" | "address" | "offer" | "approval">("cart");
  const [addresses, setAddresses] = useState<DeliveryAddress[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState<string | null>(preferredAddressId);
  const [deliveryQuote, setDeliveryQuote] = useState<DeliveryQuote | null>(null);
  const [offers, setOffers] = useState<PaymentOffer[]>([]);
  const [bestOfferKey, setBestOfferKey] = useState("standard");
  const [selectedOfferKey, setSelectedOfferKey] = useState("standard");
  const [checkoutCartSignature, setCheckoutCartSignature] = useState<string | null>(null);
  const [showOfferChooser, setShowOfferChooser] = useState(false);
  const [couponCode, setCouponCode] = useState("");
  const [couponMessage, setCouponMessage] = useState<string | null>(null);
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState<"any" | "upi" | "card" | "netbanking" | "wallet">("upi");
  const [selectedRewardId, setSelectedRewardId] = useState<string | null>(null);
  const [checkoutState, setCheckoutState] = useState<
    "idle" | "locking" | "ready" | "opening" | "paid"
  >("idle");
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [whatsappOptIn, setWhatsappOptIn] = useState(false);
  const [whatsappDestination, setWhatsappDestination] = useState("");
  const [whatsappState, setWhatsappState] = useState<WhatsAppHandoff | null>(null);
  const [whatsappLoading, setWhatsappLoading] = useState(false);
  const [whatsappError, setWhatsappError] = useState<string | null>(null);
  const [addonPrimary, setAddonPrimary] = useState<Product | null>(null);
  const [addonMatches, setAddonMatches] = useState<AddonMatch[]>([]);
  const [addonsLoading, setAddonsLoading] = useState(false);
  const [bundleRejected, setBundleRejected] = useState(false);
  const [receipt, setReceipt] = useState<PaymentReceipt | null>(null);
  const [rescueResult, setRescueResult] = useState<string | null>(null);
  const cartSignature = lines
    .map(({ product, quantity }) => `${product.id}:${quantity}`)
    .sort()
    .join("|");
  const [renderedCartSignature, setRenderedCartSignature] = useState(cartSignature);

  // React-supported derived-state reset: cart edits immediately revoke every
  // checkout artifact that was calculated for the previous quantities.
  if (renderedCartSignature !== cartSignature && !receipt) {
    setRenderedCartSignature(cartSignature);
    setApproval(null);
    setCheckoutCartId(null);
    setCheckoutCartSignature(null);
    setCheckoutStep("cart");
    setDeliveryQuote(null);
    setOffers([]);
    setBestOfferKey("standard");
    setSelectedOfferKey("standard");
    setSelectedRewardId(null);
    setShowOfferChooser(false);
    setCouponCode("");
    setCouponMessage(null);
    setCheckoutState("idle");
    setRescueResult(null);
    setWhatsappState(null);
    setCheckoutError("Cart updated. Delivery, savings and approval need a fresh check.");
  }

  useEffect(() => {
    let active = true;
    void getAddresses().then((saved) => {
      if (!active) return;
      const selected = saved.find((address) => address.id === preferredAddressId)
        || saved.find((address) => address.is_default)
        || saved[0];
      setAddresses(saved);
      setSelectedAddressId(selected?.id || null);
    }).catch(() => undefined);
    return () => { active = false; };
  }, [preferredAddressId]);

  useEffect(() => {
    let active = true;
    const loadAddons = async () => {
      if (!lines.length || approval) return;
      setAddonsLoading(true);
      try {
        for (const line of lines) {
          const response = await getCompatibleAddons(line.product.id, 3);
          const matches = response.items
            .map((item) => ({
              ...item,
              product: products.find((product) => product.id === item.product_id),
            }))
            .filter((item): item is AddonMatch => Boolean(item.product));
          if (matches.length) {
            if (active) {
              setAddonPrimary(line.product);
              setAddonMatches(matches);
            }
            return;
          }
        }
      } catch {
        // The cart remains fully usable when growth suggestions are unavailable.
      } finally {
        if (active) setAddonsLoading(false);
      }
    };
    void loadAddons();
    return () => { active = false; };
  }, [approval, lines]);

  const acceptedAddons = addonMatches.filter((match) =>
    lines.some((line) => line.product.id === match.product.id),
  );
  const beginDelivery = async () => {
    setCheckoutState("locking");
    setCheckoutError(null);
    try {
      const proposed = await createCheckoutCart(
        lines.map(({ product, quantity }) => ({ productId: product.id, quantity })),
        addonPrimary
          ? acceptedAddons.map((match) => ({
              primaryProductId: addonPrimary.id,
              addonProductId: match.product.id,
            }))
          : [],
      );
      const saved = await getAddresses();
      const selected = saved.find((address) => address.id === preferredAddressId)
        || saved.find((address) => address.is_default)
        || saved[0];
      setCheckoutCartId(proposed.id);
      setCheckoutCartSignature(cartSignature);
      setAddresses(saved);
      setSelectedAddressId(selected?.id || null);
      onScope({ cartId: proposed.id, orderId: null });
      if (!selected) {
        setCheckoutStep("address");
        setCheckoutError("Choose or add a delivery address in Niyam chat first.");
      } else {
        const quote = await confirmDelivery(proposed.id, selected.id);
        const paymentOffers = await getPaymentOffers(proposed.id);
        setDeliveryQuote(quote);
        setOffers(paymentOffers.items);
        setBestOfferKey(paymentOffers.best_offer_key);
        setSelectedOfferKey(paymentOffers.best_offer_key);
        setShowOfferChooser(false);
        setCouponCode("");
        setCouponMessage(null);
        setCheckoutStep("offer");
      }
      setCheckoutState("idle");
    } catch (error) {
      setCheckoutState("idle");
      const message = error instanceof Error ? error.message : "Checkout could not begin.";
      setCheckoutError(message);
    }
  };

  const confirmAddress = async () => {
    if (!checkoutCartId || !selectedAddressId) return;
    setCheckoutState("locking");
    setCheckoutError(null);
    try {
      const quote = await confirmDelivery(checkoutCartId, selectedAddressId);
      const paymentOffers = await getPaymentOffers(checkoutCartId);
      setDeliveryQuote(quote);
      setOffers(paymentOffers.items);
      setBestOfferKey(paymentOffers.best_offer_key);
      setSelectedOfferKey(paymentOffers.best_offer_key);
      setShowOfferChooser(false);
      setCouponCode("");
      setCouponMessage(null);
      onPreferredAddressChange(selectedAddressId);
      setCheckoutStep("offer");
    } catch (error) {
      setCheckoutError(error instanceof Error ? error.message : "Delivery could not be confirmed.");
    } finally {
      setCheckoutState("idle");
    }
  };

  const lockFinalCart = async () => {
    if (!checkoutCartId) return;
    setCheckoutState("locking");
    setCheckoutError(null);
    try {
      await selectPaymentOffer(checkoutCartId, selectedOfferKey, selectedPaymentMethod);
      const frozen = await finalizeCheckoutCart(checkoutCartId);
      setApproval(frozen);
      setCheckoutStep("approval");
      setCheckoutState("ready");
    } catch (error) {
      setCheckoutState("idle");
      setCheckoutError(error instanceof Error ? error.message : "The final cart could not be locked.");
    }
  };

  const approveAndPay = async () => {
    if (!approval) return;
    setCheckoutState("opening");
    setCheckoutError(null);
    try {
      const verified = await approveAndOpenCheckout(approval);
      setReceipt(verified);
      onScope({ cartId: approval.id, orderId: verified.orderId });
      saveOrder({
        ...verified,
        cartId: approval.id,
        cartHash: approval.cart_hash,
        items: lines.map(({ product, quantity }) => ({
          productId: product.id,
          name: product.name,
          image: product.image,
          quantity,
          unitPricePaise: product.pricePaise,
        })),
        whatsappStatus: whatsappOptIn ? "Review message prepared" : "Not requested",
      });
      setCheckoutState("paid");
      onPaymentComplete();
      if (whatsappOptIn && whatsappState) {
        try {
          const confirmation = await prepareWhatsAppConfirmation(
            verified.orderId,
            whatsappDestination,
          );
          setWhatsappState(confirmation);
          updateOrderWhatsApp(verified.orderId, confirmation.message);
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
    if (!/^\+[1-9]\d{7,14}$/.test(whatsappDestination)) {
      setWhatsappError("Enter the destination in +919876543210 format.");
      return;
    }
    setWhatsappLoading(true);
    setWhatsappError(null);
    try {
      setWhatsappState(
        await prepareWhatsAppReview(
          approval.id,
          approval.cart_hash,
          whatsappDestination,
        ),
      );
    } catch (error) {
      setWhatsappError(error instanceof Error ? error.message : "Handoff could not be prepared.");
    } finally {
      setWhatsappLoading(false);
    }
  };

  const copyHandoff = async () => {
    if (whatsappState?.share_text) await navigator.clipboard.writeText(whatsappState.share_text);
  };

  const runRescueDemo = async () => {
    if (!approval) return;
    setCheckoutError(null);
    try {
      const rescued = await demonstrateCartRescue(approval.id);
      const change = rescued.changes[0];
      setRescueResult(
        `${change.old_product_name} → ${change.new_product_name}. Previous approval revoked; the replacement cart requires fresh review and approval.`,
      );
      onScope({ cartId: rescued.replacement_cart_id, orderId: null });
    } catch (error) {
      setCheckoutError(error instanceof Error ? error.message : "Cart rescue could not run.");
    }
  };

  const selectedOffer = offers.find((offer) => offer.key === selectedOfferKey);
  const checkoutMatchesCart = checkoutCartSignature === cartSignature;
  const activeOffer = checkoutMatchesCart ? selectedOffer : undefined;
  const displayTotal = activeOffer?.expected_payable_paise
    ?? (checkoutMatchesCart ? approval?.total_paise : undefined)
    ?? subtotal + (checkoutMatchesCart ? deliveryQuote?.delivery_paise || 0 : 0);
  const selectableOffers = offers.filter((offer) => offer.provider_configured && offer.eligible);
  const unavailableOffers = offers.filter((offer) => !offer.provider_configured || !offer.eligible);
  const applyCoupon = () => {
    const normalized = couponCode.trim().toUpperCase();
    const offer = offers.find((item) => item.code?.toUpperCase() === normalized);
    if (!offer) {
      setCouponMessage("That coupon code is not available for this cart.");
      return;
    }
    if (!offer.eligible || !offer.provider_configured) {
      setCouponMessage(offer.reason);
      return;
    }
    setSelectedOfferKey(offer.key);
    setCouponCode(offer.code || "");
    setCouponMessage(`${offer.code} applied. You save ${formatMoney(offer.savings_paise)}.`);
    setShowOfferChooser(false);
  };

  return (
    <div className="drawer-layer">
      <button className="drawer-backdrop" onClick={close} aria-label="Close cart" />
      <aside className="cart-drawer">
        <div className="drawer-header"><div><span className="kicker">YOUR SELECTION</span><h2>Review cart</h2></div><button onClick={close}><X size={21} /></button></div>
        {checkoutState === "paid" && receipt ? <div className="paid-cart-state"><div className="paid-celebration"><span><Check size={24} /></span><div><small>ORDER CONFIRMED</small><h3>Your payment is verified</h3><p>The purchased products have been removed from your active cart.</p></div></div><PaymentReceiptCard receipt={receipt} whatsappState={whatsappState} /><div className="paid-cart-actions"><Link href="/orders">View My Orders <ArrowRight size={15} /></Link><button onClick={close}>Continue shopping</button></div></div> : <>
        <div className="cart-lines">
          {!lines.length && <div className="empty-cart"><ShoppingBag size={32} /><h3>Your cart is empty</h3><p>Add a product or ask Niyam to build a cart for you.</p></div>}
          {lines.map(({ product, quantity }) => (
            <div className="cart-line" key={product.id}>
              <span className="line-visual" style={{ background: product.accent }}><img src={product.image} alt="" /></span>
              <div className="line-copy"><b>{product.name}</b><small>{formatMoney(product.pricePaise)} each</small><div className="quantity-control"><button onClick={() => updateCart(product.id, -1)}>{quantity === 1 ? <Trash2 size={14} /> : <Minus size={14} />}</button><b>{quantity}</b><button onClick={() => updateCart(product.id, 1)}><Plus size={14} /></button></div></div>
              <strong>{formatMoney(product.pricePaise * quantity)}</strong>
            </div>
          ))}
          {!!addresses.length && checkoutStep === "cart" && <div className="cart-delivery-bar"><span><b>Deliver to</b><small>Change anytime before cart lock</small></span><select aria-label="Cart delivery address" value={selectedAddressId || ""} onChange={(event) => { setSelectedAddressId(event.target.value); onPreferredAddressChange(event.target.value); }}><option value="" disabled>Select address</option>{addresses.map((address) => <option value={address.id} key={address.id}>{address.label}{address.is_default ? " · Default" : ""} — {address.locality}, {address.city}</option>)}</select><button onClick={onManageAddress}>Manage</button></div>}
          {!!lines.length && !approval && (
            <GrowthBundleCard
              primary={addonPrimary}
              matches={addonMatches}
              cart={Object.fromEntries(lines.map((line) => [line.product.id, line.quantity]))}
              subtotal={subtotal}
              loading={addonsLoading}
              rejected={bundleRejected}
              onReject={() => setBundleRejected(true)}
              onOpen={onOpen}
              onAdd={(productId) => {
                setBundleRejected(false);
                updateCart(productId, 1);
              }}
            />
          )}
          {checkoutStep === "address" && <section className="checkout-step-card compact-address-card"><div className="step-title"><span>1</span><div><b>Delivery address</b><small>Manage full addresses and voice selection inside Niyam chat.</small></div></div>{!!addresses.length && <select aria-label="Delivery address" value={selectedAddressId || ""} onChange={(event) => { setSelectedAddressId(event.target.value); onPreferredAddressChange(event.target.value); }}><option value="" disabled>Select an address</option>{addresses.map((address) => <option value={address.id} key={address.id}>{address.label}{address.is_default ? " · Default" : ""} — {address.locality}, {address.city} · {address.pincode.slice(0, 3)}***</option>)}</select>}<button className="manage-address-link" onClick={onManageAddress}>Manage addresses in Niyam chat</button>{selectedAddressId && <button className="step-primary" onClick={() => void confirmAddress()} disabled={checkoutState === "locking"}>{checkoutState === "locking" ? "Checking delivery…" : "Use this address"}<ArrowRight size={15} /></button>}</section>}
          {checkoutStep === "offer" && deliveryQuote && (
            <section className="checkout-step-card">
              <div className="delivery-confirmed"><Check size={15} /><span><b>{deliveryQuote.address_label} confirmed · {deliveryQuote.city} {deliveryQuote.masked_pincode}</b><small>{deliveryQuote.delivery_paise ? formatMoney(deliveryQuote.delivery_paise) : "Free delivery"} · {deliveryQuote.eta_min_days}–{deliveryQuote.eta_max_days} days</small></span><button onClick={() => setCheckoutStep("address")}>Change</button></div>
              <div className="step-title"><span>2</span><div><b>Offers &amp; payment</b><small>The best eligible cart saving is applied automatically. You can change it before locking the cart.</small></div></div>
              {activeOffer && <div className="applied-offer-card"><div className="applied-offer-icon"><Check size={17} /></div><div><small>{activeOffer.savings_paise ? "BEST OFFER APPLIED" : "NO COUPON APPLIED"}</small><b>{activeOffer.title}</b>{activeOffer.code && <code>{activeOffer.code}</code>}<span>{activeOffer.savings_paise ? `You save ${formatMoney(activeOffer.savings_paise)} · Pay ${formatMoney(activeOffer.expected_payable_paise)}` : "Pay the regular cart total"}</span></div><button type="button" onClick={() => setShowOfferChooser((value) => !value)}>{showOfferChooser ? "Done" : "Change"}</button></div>}
              <div className="coupon-entry"><div><b>Have a coupon code?</b><small>Try SMART100, FESTIVE8 or BUNDLE150 when the cart qualifies.</small></div><span><input value={couponCode} onChange={(event) => { setCouponCode(event.target.value.toUpperCase()); setCouponMessage(null); }} onKeyDown={(event) => { if (event.key === "Enter") applyCoupon(); }} placeholder="Enter coupon" aria-label="Coupon code" /><button type="button" onClick={applyCoupon}>Apply</button></span>{couponMessage && <em className={couponMessage.includes("applied") ? "success" : ""}>{couponMessage}</em>}</div>
              {showOfferChooser && <div className="offer-marketplace"><div className="offer-marketplace-heading"><b>Available for this cart</b><small>{selectableOffers.length} selectable offers</small></div>{selectableOffers.map((offer) => <button type="button" className={selectedOfferKey === offer.key ? "selected" : ""} onClick={() => { setSelectedOfferKey(offer.key); setCouponCode(offer.code || ""); setCouponMessage(null); }} key={offer.key}><span>{selectedOfferKey === offer.key ? <Check size={14} /> : <span className="offer-radio" />}</span><p><b>{offer.title}{offer.key === bestOfferKey && offer.savings_paise > 0 ? " · Best saving" : ""}</b><small>{offer.terms}</small>{offer.code && <code>{offer.code}</code>}</p><em>{offer.savings_paise ? `−${formatMoney(offer.savings_paise)}` : "No saving"}</em></button>)}{!!unavailableOffers.length && <details className="unavailable-offers"><summary>{unavailableOffers.length} more bank/UPI offers</summary>{unavailableOffers.map((offer) => <p key={offer.key}><span><b>{offer.title}</b><small>{offer.reason}</small></span><em>{offer.code || "Eligibility required"}</em></p>)}</details>}</div>}
              <div className="payment-method-choices"><b>How would you prefer to pay?</b><small>Choose a preference now; Razorpay performs the final instrument selection and authentication.</small><div>{([['upi','UPI','Fastest'],['card','Credit / debit card','Bank rewards'],['netbanking','Netbanking','Choose your bank'],['wallet','Wallet','Supported wallets']] as const).map(([key, title, note]) => <button type="button" className={selectedPaymentMethod === key ? "selected" : ""} onClick={() => { setSelectedPaymentMethod(key); setSelectedRewardId(null); }} key={key}><span>{title}</span><small>{note}</small>{selectedPaymentMethod === key && <Check size={14} />}</button>)}</div></div>
              <PaymentRewardPicker key={selectedPaymentMethod} amountPaise={activeOffer?.expected_payable_paise ?? subtotal} selectedId={selectedRewardId} methodFilter={selectedPaymentMethod} onSelect={(reward) => { setSelectedRewardId(reward.id); setSelectedPaymentMethod(reward.type); }} />
              <button className="step-primary" onClick={() => void lockFinalCart()} disabled={checkoutState === "locking"}>{checkoutState === "locking" ? "Locking exact cart…" : "Confirm choice & lock final cart"}<ArrowRight size={15} /></button>
            </section>
          )}
        </div>
        {!!lines.length && <div className="cart-summary">
          <div><span>Subtotal</span><b>{formatMoney(subtotal)}</b></div>
          <div><span>Delivery</span><b className="free">{checkoutMatchesCart && deliveryQuote?.delivery_paise ? formatMoney(deliveryQuote.delivery_paise) : "Free"}</b></div>
          {activeOffer?.savings_paise ? <div className="discount-line"><span>Offer saving</span><b>−{formatMoney(activeOffer.savings_paise)}</b></div> : null}
          <div className="total-line"><span>Final payable</span><strong>{formatMoney(displayTotal)}</strong></div>
          <div className="approval-box"><ShieldCheck size={19} /><p><b>You remain in control</b><small>We’ll lock and show the exact cart again before opening Razorpay test checkout.</small></p></div>
          {approval && checkoutState !== "paid" && (
            <div className="exact-approval">
              <span>Exact cart awaiting your approval</span>
              <b>{formatMoney(displayTotal)}</b>
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
          {approval && checkoutState !== "paid" && <div className="rescue-demo"><div><b>Self-healing cart rescue</b><small>Judge demo: simulate one unavailable item, preserve intent, and revoke this approval.</small></div><button onClick={() => void runRescueDemo()}>Run rescue demo</button>{rescueResult && <p>{rescueResult}</p>}</div>}
          {approval && (
            <div className="whatsapp-box">
              <label><input type="checkbox" checked={whatsappOptIn} onChange={(event) => { setWhatsappOptIn(event.target.checked); setWhatsappState(null); setWhatsappError(null); }} /><span><b><MessageCircle size={15} /> WhatsApp updates</b><small>Optional. I consent to a cart-review message and verified-payment confirmation at the number I confirm below.</small></span></label>
              {whatsappOptIn && !whatsappState && <><input className="whatsapp-destination" type="tel" inputMode="tel" autoComplete="tel" value={whatsappDestination} onChange={(event) => { setWhatsappDestination(event.target.value.trim()); setWhatsappError(null); }} placeholder="+919876543210" aria-label="Confirmed WhatsApp destination" /><small>Sandbox only: this phone must have sent the Twilio join message within 24 hours. NiyamCart does not store the raw number.</small><button onClick={prepareWhatsApp} disabled={whatsappLoading || !/^\+[1-9]\d{7,14}$/.test(whatsappDestination)}>{whatsappLoading ? "Sending…" : "Confirm number & send review"}</button></>}
              {whatsappState && <div className="handoff-result" role="status"><small>{whatsappState.message}</small>{whatsappState.share_text && <button onClick={copyHandoff}><Copy size={13} /> Copy message</button>}</div>}
              {whatsappError && <small className="checkout-error" role="alert">{whatsappError}</small>}
            </div>
          )}
          {approval ? (
            <button className="checkout-button" onClick={approveAndPay} disabled={checkoutState === "opening"}>
              {checkoutState === "opening" ? "Opening secure checkout…" : "Approve exact cart & pay"}
              <ArrowRight size={18} />
            </button>
          ) : (
            <button className="checkout-button" onClick={beginDelivery} disabled={checkoutState === "locking" || checkoutStep !== "cart"}>
              {checkoutState === "locking" ? "Preparing checkout…" : checkoutStep === "cart" ? "Continue to offers" : "Complete the step above"}
              <ArrowRight size={18} />
            </button>
          )}
          {checkoutError && <p className="checkout-error" role="alert">{checkoutError}{checkoutError.toLowerCase().includes("sign in") && <Link href={`/auth?next=${encodeURIComponent("/#shop")}`}>Sign in to continue</Link>}</p>}
          <small className="test-mode" aria-live="polite">Razorpay test mode · No real money charged</small>
        </div>}
        </>}
      </aside>
    </div>
  );
}

function GrowthBundleCard({ primary, matches, cart, subtotal, loading, rejected, onReject, onAdd, onOpen }: { primary: Product | null; matches: AddonMatch[]; cart: Cart; subtotal: number; loading: boolean; rejected: boolean; onReject: () => void; onAdd: (productId: string) => void; onOpen: (product: Product) => void }) {
  const recordedExposure = useRef<string | null>(null);
  useEffect(() => {
    const first = matches[0];
    if (!primary || !first || recordedExposure.current === first.product.id) return;
    recordedExposure.current = first.product.id;
    void recordGrowthEvent({
      primary_product_id: primary.id,
      addon_product_id: first.product.id,
      event_type: "exposed",
      baseline_paise: subtotal,
      suggested_paise: subtotal + first.product.pricePaise,
    }).catch(() => undefined);
  }, [matches, primary, subtotal]);
  if (loading) return <div className="growth-card growth-loading"><LoaderCircle className="spin" size={17} /> Finding compatible add-ons…</div>;
  if (!primary || !matches.length) return null;

  const accepted = matches.filter((match) => cart[match.product.id]);
  const available = matches.filter((match) => !cart[match.product.id]).slice(0, 2);
  const acceptedValue = accepted.reduce(
    (sum, match) => sum + match.product.pricePaise * (cart[match.product.id] || 0),
    0,
  );
  const baseline = Math.max(0, subtotal - acceptedValue);
  const previewAddon = available[0]?.product.pricePaise || 0;
  const suggested = accepted.length ? subtotal : subtotal + previewAddon;
  const increase = baseline > 0 ? ((suggested - baseline) / baseline) * 100 : 0;
  const decision = accepted.length ? "Accepted" : rejected ? "Rejected · cart unchanged" : "Awaiting buyer choice";

  return (
    <section className="growth-card" aria-label="Compatible bundle suggestion">
      <div className="growth-heading">
        <span><TrendingUp size={17} /></span>
        <div><b>Complete the look</b><small>Compatible with {primary.name}</small></div>
      </div>
      {!rejected && available.map((match) => (
        <article className="addon-row" key={match.product.id}>
          <button className="addon-visual" type="button" aria-label={`View ${match.product.name}`} onClick={() => onOpen(match.product)}>
            <img src={match.product.image} alt="" />
          </button>
          <div><b>{match.product.name}</b><span className="compatibility-score">{match.match_score}/100 compatibility</span><small>{match.reason}</small><details className="compatibility-evidence"><summary>Why it pairs</summary>{match.evidence.map((item) => <p key={item}><Check size={11} /> {item}</p>)}</details><strong>{formatMoney(match.product.pricePaise)}</strong></div>
          <button onClick={() => { void recordGrowthEvent({ primary_product_id: primary.id, addon_product_id: match.product.id, event_type: "accepted", baseline_paise: subtotal, suggested_paise: subtotal + match.product.pricePaise }).catch(() => undefined); onAdd(match.product.id); }}><Plus size={14} /> Add</button>
        </article>
      ))}
      <div className="growth-metrics">
        <div><small>Baseline cart</small><b>{formatMoney(baseline)}</b></div>
        <ArrowRight size={14} />
        <div><small>Suggested bundle</small><b>{formatMoney(suggested)}</b></div>
        <div className="aov-metric"><small>Potential AOV</small><b>+{increase.toFixed(1)}%</b></div>
      </div>
      <div className={`growth-decision ${accepted.length ? "accepted" : rejected ? "rejected" : ""}`}>
        <span>Upsell {decision.toLowerCase()}</span>
        {!accepted.length && !rejected && <button onClick={() => { const first = available[0]; if (first) void recordGrowthEvent({ primary_product_id: primary.id, addon_product_id: first.product.id, event_type: "rejected", baseline_paise: subtotal, suggested_paise: subtotal + first.product.pricePaise }).catch(() => undefined); onReject(); }}>Not now</button>}
      </div>
      <small className="growth-boundary"><ShieldCheck size={13} /> Suggestions never change your cart automatically.</small>
    </section>
  );
}

function PaymentReceiptCard({ receipt, whatsappState }: { receipt: PaymentReceipt; whatsappState: WhatsAppHandoff | null }) {
  const whatsappLabel = whatsappState?.status === "sent"
    ? "Confirmation sent"
    : whatsappState
      ? whatsappState.message
      : "Not requested";
  return (
    <section className="receipt-card" role="status" aria-live="polite">
      <div className="receipt-heading"><span><Check size={18} /></span><div><b>Payment verified</b><small>Razorpay evidence matched the locked cart</small></div></div>
      <dl>
        <div><dt>Order ID</dt><dd title={receipt.orderId}>{receipt.orderId}</dd></div>
        <div><dt>Verified amount</dt><dd>{formatMoney(receipt.amountPaise)}</dd></div>
        <div><dt>Razorpay test payment</dt><dd title={receipt.paymentId}>{receipt.paymentId}</dd></div>
        <div><dt>Verified at</dt><dd>{serverTimestamp(receipt.verifiedAt).toLocaleString("en-IN")}</dd></div>
        <div><dt>WhatsApp</dt><dd>{whatsappLabel}</dd></div>
      </dl>
      <div className="test-receipt"><ShieldCheck size={14} /><b>TEST MODE · No real money charged</b></div>
    </section>
  );
}

const auditLabels: Record<string, string> = {
  agent_session: "Agent decision trail",
  cart: "Cart authority",
  order: "Order & payment",
};

const auditEventSummary = (event: VerifiedAudit["events"][number]) => {
  const payload = event.payload;
  const tool = typeof payload.tool_name === "string" ? payload.tool_name.replaceAll("_", " ") : null;
  if (event.event_type === "tool_call") return `${tool || "Catalogue tool"} requested within a bounded step.`;
  if (event.event_type === "tool_result") {
    const count = Array.isArray(payload.products) ? payload.products.length : payload.product ? 1 : 0;
    return `${tool || "Catalogue tool"} returned ${count || "typed"} grounded result${count === 1 ? "" : "s"}.`;
  }
  if (event.event_type === "policy_decision") return `${String(payload.decision || "checked").toUpperCase()} · ${String(payload.rule_id || "policy rule recorded")}`;
  if (event.event_type === "cart_proposed") return `Cart proposed with ${String(payload.line_count || "recorded")} line(s) and authoritative catalogue prices.`;
  if (event.event_type === "cart_frozen") return `Exact cart locked at ${formatMoney(Number(payload.total_paise || 0))}.`;
  if (event.event_type === "cart_approved") return "Buyer approved the exact locked-cart hash.";
  if (event.event_type === "order_created") return `Test order created for ${formatMoney(Number(payload.total_paise || 0))}.`;
  if (event.event_type === "provider_order_bound") return "Razorpay test order linked to the internal order.";
  if (event.event_type === "payment_evidence_evaluated") return `${payload.accepted ? "Accepted" : "Rejected"} Razorpay evidence; resulting state ${String(payload.resulting_status || "recorded")}.`;
  if (event.event_type === "user_message") return "Buyer request recorded.";
  if (event.event_type === "final_answer") return "Bounded response completed.";
  return event.event_type.replaceAll("_", " ");
};

function TrustAuditDrawer({ agentSessionId, cartId, orderId, close, onRunFailureDemo }: { agentSessionId: string | null; cartId: string | null; orderId: string | null; close: () => void; onRunFailureDemo: () => Promise<void> }) {
  const [audits, setAudits] = useState<VerifiedAudit[]>([]);
  const [loading, setLoading] = useState(true);
  const [demoLoading, setDemoLoading] = useState(false);

  useEffect(() => {
    let active = true;
    const scopes = [
      agentSessionId ? (["agent_session", agentSessionId] as const) : null,
      cartId ? (["cart", cartId] as const) : null,
      orderId ? (["order", orderId] as const) : null,
    ].filter((scope): scope is readonly ["agent_session" | "cart" | "order", string] => Boolean(scope));
    const load = async () => {
      setLoading(true);
      const settled = await Promise.allSettled(scopes.map(([type, id]) => getVerifiedAudit(type, id)));
      if (active) {
        setAudits(settled.flatMap((result) => result.status === "fulfilled" ? [result.value] : []));
        setLoading(false);
      }
    };
    void load();
    return () => { active = false; };
  }, [agentSessionId, cartId, orderId]);

  const verified = audits.filter((audit) => audit.valid).length;
  const events = audits.reduce((total, audit) => total + audit.event_count, 0);
  const runDemo = async () => {
    setDemoLoading(true);
    await onRunFailureDemo();
    setDemoLoading(false);
  };

  return (
    <div className="drawer-layer audit-layer">
      <button className="drawer-backdrop" onClick={close} aria-label="Close Trust and Audit" />
      <aside className="audit-drawer" aria-label="Trust and Audit judge view">
        <header className="audit-header"><div><span className="judge-badge">JUDGE VIEW</span><h2>Trust & Audit</h2><p>Explainable evidence without exposing hidden model reasoning.</p></div><button onClick={close} aria-label="Close Trust and Audit"><X size={20} /></button></header>
        <div className="audit-body">
          <section className="audit-overview">
            <div><ShieldCheck size={18} /><span><b>{verified}/{audits.length || 0}</b><small>Verified chains</small></span></div>
            <div><FileCheck2 size={18} /><span><b>{events}</b><small>Evidence events</small></span></div>
            <div><Gauge size={18} /><span><b>Gated</b><small>Money authority</small></span></div>
          </section>
          <section className="failure-demo">
            <div><LockKeyhole size={20} /><span><b>Graceful-failure demo</b><small>Requests an automatic purchase. Niyam must refuse with zero commerce side effects.</small></span></div>
            <button onClick={() => void runDemo()} disabled={demoLoading}>{demoLoading ? <><LoaderCircle className="spin" size={14} /> Running…</> : "Run safe refusal"}</button>
          </section>
          {loading && <div className="audit-empty"><LoaderCircle className="spin" size={20} /> Verifying evidence chains…</div>}
          {!loading && !audits.length && <div className="audit-empty"><Hash size={22} /><b>No commerce evidence yet</b><p>Ask Niyam a product question or run the refusal demo. Locking and paying a cart adds cart and order evidence.</p></div>}
          {audits.map((audit) => (
            <section className="audit-scope" key={`${audit.scope_type}:${audit.scope_id}`}>
              <div className="audit-scope-heading"><div><span>{auditLabels[audit.scope_type] || audit.scope_type}</span><small title={audit.scope_id}>{audit.scope_id}</small></div><b className={audit.valid ? "verified" : "invalid"}><ShieldCheck size={13} /> {audit.valid ? "Hash chain verified" : "Integrity warning"}</b></div>
              <div className="audit-root"><Hash size={13} /><code title={audit.root_hash}>{audit.root_hash || "Chain starts with the next event"}</code></div>
              <ol className="audit-timeline">
                {audit.events.map((event) => (
                  <li key={`${event.sequence}:${event.event_hash}`}><span>{event.sequence}</span><div><b>{event.event_type.replaceAll("_", " ")}</b><p>{auditEventSummary(event)}</p><small>{serverTimestamp(event.created_at).toLocaleString("en-IN")}</small></div></li>
                ))}
              </ol>
            </section>
          ))}
        </div>
      </aside>
    </div>
  );
}
