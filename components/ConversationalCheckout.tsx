"use client";

import { ArrowRight, Check, MapPin, Mic, Navigation, Plus, ShieldCheck, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { transcribeVoice } from "@/lib/agent";
import { formatMoney, type Product } from "@/lib/catalog";
import { getAddresses, reverseGeocode, saveAddress, type DeliveryAddress } from "@/lib/checkout";

type CartLine = { product: Product; quantity: number };

export function ConversationalCheckout({ lines, subtotal, preferredAddressId, onPreferredAddressChange, onReadyForCheckout, onAddMore }: {
  lines: CartLine[];
  subtotal: number;
  preferredAddressId: string | null;
  onPreferredAddressChange: (addressId: string) => void;
  onReadyForCheckout: () => void;
  onAddMore: () => void;
}) {
  const [stage, setStage] = useState<"review" | "address" | "confirmed">("review");
  const [addresses, setAddresses] = useState<DeliveryAddress[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState<string | null>(preferredAddressId);
  const [showAddressForm, setShowAddressForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [pendingCoordinates, setPendingCoordinates] = useState<{ latitude: number; longitude: number } | null>(null);
  const [recording, setRecording] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const signature = lines.map(({ product, quantity }) => `${product.id}:${quantity}`).join("|");
  const previousSignature = useRef(signature);
  const [draft, setDraft] = useState({ label: "Home", recipient_name: "", phone: "+91", line1: "", locality: "", landmark: "", city: "", state: "", pincode: "", latitude: null as number | null, longitude: null as number | null, is_default: true });

  useEffect(() => {
    if (previousSignature.current !== signature) {
      previousSignature.current = signature;
      setStage("review");
      setMessage("Your selection changed. Review the products again before delivery.");
    }
  }, [signature]);

  const approveProducts = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const saved = await getAddresses();
      const next = saved.find((item) => item.id === preferredAddressId) || saved.find((item) => item.is_default) || saved[0];
      setAddresses(saved);
      setSelectedAddressId(next?.id || null);
      setShowAddressForm(!saved.length);
      setStage("address");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Delivery addresses could not be loaded.");
    } finally {
      setBusy(false);
    }
  };

  const storeAddress = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const saved = await saveAddress({ ...draft, landmark: draft.landmark || null });
      setAddresses((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      setSelectedAddressId(saved.id);
      setShowAddressForm(false);
      setMessage(`${saved.label} saved. Check the masked address and confirm it below.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Address could not be saved.");
    } finally {
      setBusy(false);
    }
  };

  const requestCurrentLocation = () => {
    if (!navigator.geolocation) {
      setMessage("Current location is not supported in this browser. Add the address manually.");
      setShowAddressForm(true);
      return;
    }
    setMessage("Requesting browser location permission…");
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      setPendingCoordinates({ latitude: coords.latitude, longitude: coords.longitude });
      setDraft((current) => ({ ...current, latitude: coords.latitude, longitude: coords.longitude }));
      setMessage("Location detected. Confirm before sharing it with OpenStreetMap.");
    }, () => setMessage("Location permission was not granted. Choose a saved address or add one."));
  };

  const lookupCurrentAddress = async () => {
    if (!pendingCoordinates) return;
    setBusy(true);
    setMessage("Finding an approximate address…");
    try {
      const found = await reverseGeocode(pendingCoordinates.latitude, pendingCoordinates.longitude, true);
      setDraft((current) => ({ ...current, ...found, label: "Current", latitude: pendingCoordinates.latitude, longitude: pendingCoordinates.longitude }));
      setPendingCoordinates(null);
      setShowAddressForm(true);
      setMessage("Approximate address found. Complete the house details, then save it.");
    } catch (error) {
      setShowAddressForm(true);
      setMessage(error instanceof Error ? error.message : "Address lookup failed. Complete it manually.");
    } finally {
      setBusy(false);
    }
  };

  const toggleVoice = async () => {
    if (recording) {
      recorderRef.current?.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      streamRef.current = stream;
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data); };
      recorder.onstop = async () => {
        setRecording(false);
        streamRef.current?.getTracks().forEach((track) => track.stop());
        try {
          const transcript = await transcribeVoice(new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" }));
          const command = `${transcript.transcript} ${transcript.normalized_text}`.toLowerCase();
          const saved = addresses.find((item) => command.includes(item.label.toLowerCase()));
          if (saved) {
            setSelectedAddressId(saved.id);
            setMessage(`${saved.label} selected by voice. Check it and tap Confirm address.`);
          } else if (command.includes("current location") || command.includes("my location")) {
            requestCurrentLocation();
          } else if (command.includes("new address") || command.includes("add address")) {
            setShowAddressForm(true);
            setMessage("New address form opened. Complete and save it.");
          } else {
            setMessage(`Heard “${transcript.transcript}”. Say a saved label such as Home or Work.`);
          }
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "Voice address could not be understood.");
        }
      };
      recorder.start();
      setRecording(true);
      setMessage("Listening for Home, Work, current location, or new address…");
    } catch {
      setMessage("Microphone permission was not granted. Select the address below.");
    }
  };

  const confirmAddress = () => {
    if (!selectedAddressId) return;
    onPreferredAddressChange(selectedAddressId);
    setStage("confirmed");
    setMessage(null);
  };
  const selected = addresses.find((item) => item.id === selectedAddressId);

  return <section className="chat-checkout" aria-label="Conversational checkout">
    <div className="chat-checkout-heading"><span><Check size={16} /></span><div><b>{stage === "review" ? "Ready to review your products?" : stage === "address" ? "Where should we deliver?" : "Delivery address selected"}</b><small>{lines.reduce((sum, line) => sum + line.quantity, 0)} items · {formatMoney(subtotal)}</small></div></div>
    {stage === "review" && <><div className="chat-product-summary">{lines.slice(0, 3).map(({ product, quantity }) => <span key={product.id}>{quantity}× {product.name}</span>)}</div><div className="chat-checkout-actions"><button className="primary" onClick={() => void approveProducts()} disabled={busy}>{busy ? "Loading addresses…" : "Approve products"}<ArrowRight size={14} /></button><button onClick={onAddMore}><Plus size={14} /> Add more products</button></div></>}
    {stage === "address" && <>
      {!!addresses.length && <div className="chat-address-options">{addresses.map((address) => <label className={selectedAddressId === address.id ? "selected" : ""} key={address.id}><input type="radio" name="chat-delivery-address" checked={selectedAddressId === address.id} onChange={() => setSelectedAddressId(address.id)} /><span><b>{address.label}{address.is_default ? " · Default" : ""}</b><small>{address.locality}, {address.city} · {address.pincode.slice(0, 3)}***</small></span></label>)}</div>}
      <div className="chat-address-actions"><button onClick={() => setShowAddressForm((value) => !value)}><Plus size={13} /> Add new</button><button onClick={requestCurrentLocation}><Navigation size={13} /> Current location</button><button onClick={() => void toggleVoice()}>{recording ? <Square size={12} fill="currentColor" /> : <Mic size={13} />}{recording ? " Stop" : " Speak"}</button></div>
      {pendingCoordinates && <div className="location-consent"><ShieldCheck size={16} /><p><b>Share location with OpenStreetMap?</b><small>Only coordinates are sent for approximate lookup—not to the shopping model or audit trail.</small></p><button onClick={() => void lookupCurrentAddress()} disabled={busy}>Find address</button><button onClick={() => { setPendingCoordinates(null); setShowAddressForm(true); setMessage("Coordinates were not shared. Enter the address manually."); }}>Enter manually</button></div>}
      {showAddressForm && <div className="chat-address-form">
        <input aria-label="Address label" placeholder="Home / Work" value={draft.label} onChange={(event) => setDraft({ ...draft, label: event.target.value })} /><input aria-label="Recipient name" placeholder="Recipient name" value={draft.recipient_name} onChange={(event) => setDraft({ ...draft, recipient_name: event.target.value })} /><input aria-label="Phone" placeholder="+919876543210" value={draft.phone} onChange={(event) => setDraft({ ...draft, phone: event.target.value })} /><input aria-label="House and building" placeholder="Flat / house / building" value={draft.line1} onChange={(event) => setDraft({ ...draft, line1: event.target.value })} /><input aria-label="Locality" placeholder="Street / locality" value={draft.locality} onChange={(event) => setDraft({ ...draft, locality: event.target.value })} /><input aria-label="Landmark" placeholder="Landmark (optional)" value={draft.landmark} onChange={(event) => setDraft({ ...draft, landmark: event.target.value })} /><input aria-label="City" placeholder="City" value={draft.city} onChange={(event) => setDraft({ ...draft, city: event.target.value })} /><input aria-label="State" placeholder="State" value={draft.state} onChange={(event) => setDraft({ ...draft, state: event.target.value })} /><input aria-label="Pincode" placeholder="6-digit pincode" value={draft.pincode} onChange={(event) => setDraft({ ...draft, pincode: event.target.value.replace(/\D/g, "").slice(0, 6) })} /><button onClick={() => void storeAddress()} disabled={busy}>{busy ? "Saving…" : "Save and select"}</button>
      </div>}
      <button className="chat-confirm-address" onClick={confirmAddress} disabled={!selectedAddressId}><Check size={14} /> Confirm address</button>
    </>}
    {stage === "confirmed" && selected && <div className="chat-address-confirmed"><MapPin size={17} /><p><b>Deliver to {selected.label}</b><small>{selected.locality}, {selected.city} · {selected.pincode.slice(0, 3)}***</small></p><button onClick={() => setStage("address")}>Change</button></div>}
    {stage === "confirmed" && <button className="chat-continue-checkout" onClick={onReadyForCheckout}>Continue to offers and payment <ArrowRight size={14} /></button>}
    {message && <small className="chat-checkout-message" role="status">{message}</small>}
    <small className="chat-checkout-safety"><ShieldCheck size={12} /> Voice can select an address, but only this button confirms it.</small>
  </section>;
}
