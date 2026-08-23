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
  LoaderCircle,
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
  Trash2,
  UserRound,
  Volume2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { formatMoney, formatSpecLabel, products, searchProducts, type Product } from "@/lib/catalog";
import {
  audioDataUrl,
  continueAgent,
  getProposedCart,
  runAgent,
  transcribeVoice,
  type AgentRunOptions,
  type AgentRun,
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
type ChatTurn = { id: string; prompt: string; result: AgentRun; voiceInput: boolean };

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
  const [visibleCount, setVisibleCount] = useState(12);
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
    options: AgentRunOptions & { normalizedMessage?: string; voiceInput?: boolean } = {},
  ) => {
    const displayMessage = prompt.trim();
    const message = (options.normalizedMessage || displayMessage).trim();
    if (!message || agentLoading) return;
    setAgentQuery("");
    setPendingPrompt(displayMessage);
    setAgentLoading(true);
    setAgentError(null);
    try {
      const result = agentSessionId
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
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Niyam is temporarily unavailable.");
    } finally {
      setPendingPrompt(null);
      setAgentLoading(false);
    }
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
      setCartOpen(true);
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
                  <div className="assistant-message">
                    <div className="answer-meta"><span className="reason-label"><Sparkles size={13} /> GROUNDED RESPONSE</span>{languageName && languageName !== "English" && <span className="language-badge">{languageName}</span>}</div>
                    <p>{turn.result.answer}</p>
                    {answerAudio && <audio className="voice-answer" src={answerAudio} controls autoPlay={turn.voiceInput} preload="metadata">Your browser cannot play this response.</audio>}
                    {turn.voiceInput && !answerAudio && turn.result.voice_status === "unavailable" && <small className="voice-note"><Volume2 size={13} /> Text response shown because speech playback was unavailable.</small>}
                    {turn.result.proposed_cart_id && <button className="inline-action" onClick={() => void reviewAgentCart(turn.result.proposed_cart_id!)}>Review proposed cart <ArrowRight size={15} /></button>}
                  </div>
                  {!!recommended.length && <ProductRecommendationCarousel products={recommended} cart={cart} updateCart={updateCart} onOpen={setSelectedProduct} />}
                </div>
              );
            })}
            {pendingPrompt && <div className="user-message">{pendingPrompt}</div>}
            {recording && <div className="agent-state recording-state" role="status" aria-live="polite"><Mic size={18} /><div><b>Listening… 0:{String(recordingSeconds).padStart(2, "0")}</b><small>Speak naturally in your preferred language, then tap stop.</small></div></div>}
            {voiceProcessing && <div className="agent-state" role="status" aria-live="polite"><LoaderCircle className="spin" size={18} /><div><b>Understanding your voice</b><small>Detecting the language and preparing a catalogue-safe request.</small></div></div>}
            {agentLoading && <div className="agent-state" role="status" aria-live="polite"><LoaderCircle className="spin" size={18} /><div><b>{chatTurns.length ? "Refining your recommendations" : "Checking the live catalogue"}</b><small>Niyam remembers this conversation, but cannot order or pay.</small></div></div>}
            {agentError && <div className="agent-state error-state" role="alert"><CircleX size={18} /><div><b>Request not completed</b><small>{agentError}</small></div></div>}
          </div>
          <div className="agent-input">
            <button className={`voice-button${recording ? " recording" : ""}`} onClick={recording ? stopVoiceQuestion : () => void startVoiceQuestion()} aria-label={recording ? "Stop voice recording" : "Start voice recording"} aria-pressed={recording} disabled={agentLoading || voiceProcessing} title={recording ? "Stop recording" : "Speak in your language"}>{recording ? <Square size={15} fill="currentColor" /> : <Mic size={18} />}</button>
            <input value={agentQuery} onChange={(event) => setAgentQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && !agentLoading && !voiceProcessing && !recording && void askAgent()} placeholder={recording ? "Listening…" : "Type or speak in your language…"} disabled={agentLoading || voiceProcessing || recording} aria-label="Shopping request" />
            <button className="send-button" onClick={() => void askAgent()} aria-label="Send" disabled={agentLoading || voiceProcessing || recording || !agentQuery.trim()}>{agentLoading ? <LoaderCircle className="spin" size={18} /> : <ArrowRight size={18} />}</button>
          </div>
          <div className="panel-safety"><ShieldCheck size={13} /> 11 languages · No purchase without your approval</div>
        </aside>
      )}

      {cartOpen && <CartDrawer key={cartLines.map(({ product, quantity }) => `${product.id}:${quantity}`).join("|")} lines={cartLines} subtotal={subtotal} updateCart={updateCart} close={() => setCartOpen(false)} />}
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

function ProductRecommendationCarousel({ products: recommended, cart, updateCart, onOpen }: { products: Product[]; cart: Cart; updateCart: (id: string, delta: number) => void; onOpen: (product: Product) => void }) {
  const rail = useRef<HTMLDivElement>(null);
  const move = (direction: number) => rail.current?.scrollBy({ left: direction * 240, behavior: "smooth" });
  return (
    <section className="recommendation-block" aria-label="Niyam product recommendations">
      <div className="recommendation-heading"><div><b>Recommended for you</b><small>{recommended.length} grounded matches</small></div><span><button onClick={() => move(-1)} aria-label="Previous recommendations"><ChevronLeft size={15} /></button><button onClick={() => move(1)} aria-label="Next recommendations"><ChevronRight size={15} /></button></span></div>
      <div className="recommendation-rail" ref={rail}>
        {recommended.map((product) => {
          const quantity = cart[product.id] || 0;
          return (
            <article className="recommendation-card" key={product.id}>
              <button className="recommendation-open" onClick={() => onOpen(product)} aria-label={`View ${product.name}`}>
                <img src={product.image} alt={product.name} />
                <span className="product-category">{product.category}</span>
                <strong>{product.name}</strong>
                <small><Star size={11} fill="currentColor" /> {product.rating} · {product.stock} in stock</small>
                <b>{formatMoney(product.pricePaise)}</b>
              </button>
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

function CartDrawer({ lines, subtotal, updateCart, close }: { lines: { product: Product; quantity: number }[]; subtotal: number; updateCart: (id: string, delta: number) => void; close: () => void }) {
  const [approval, setApproval] = useState<ApprovalCart | null>(null);
  const [checkoutState, setCheckoutState] = useState<
    "idle" | "locking" | "ready" | "opening" | "paid"
  >("idle");
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [whatsappOptIn, setWhatsappOptIn] = useState(false);
  const [whatsappDestination, setWhatsappDestination] = useState("");
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
      if (whatsappOptIn && whatsappState) {
        try {
          const confirmation = await prepareWhatsAppConfirmation(
            verified.orderId,
            whatsappDestination,
          );
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
              <label><input type="checkbox" checked={whatsappOptIn} onChange={(event) => { setWhatsappOptIn(event.target.checked); setWhatsappState(null); setWhatsappError(null); }} /><span><b><MessageCircle size={15} /> WhatsApp updates</b><small>Optional. I consent to a cart-review message and verified-payment confirmation at the number I confirm below.</small></span></label>
              {whatsappOptIn && !whatsappState && <><input className="whatsapp-destination" type="tel" inputMode="tel" autoComplete="tel" value={whatsappDestination} onChange={(event) => { setWhatsappDestination(event.target.value.trim()); setWhatsappError(null); }} placeholder="+919876543210" aria-label="Confirmed WhatsApp destination" /><small>Sandbox only: this phone must have sent the Twilio join message within 24 hours. NiyamCart does not store the raw number.</small><button onClick={prepareWhatsApp} disabled={whatsappLoading || !/^\+[1-9]\d{7,14}$/.test(whatsappDestination)}>{whatsappLoading ? "Sending…" : "Confirm number & send review"}</button></>}
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
