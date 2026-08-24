"use client";

import { ArrowRight, Check, Eye, EyeOff, LockKeyhole, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getCurrentUser, login, signup } from "@/lib/auth";

type Mode = "login" | "signup";

export function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const modeTimer = params.get("mode") === "signup"
      ? window.setTimeout(() => setMode("signup"), 0)
      : null;
    void getCurrentUser().then(() => {
      router.replace(params.get("next") || "/profile");
    }).catch(() => undefined);
    return () => { if (modeTimer !== null) window.clearTimeout(modeTimer); };
  }, [router]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      if (mode === "signup") await signup(name, email, password);
      else await login(email, password);
      const next = new URLSearchParams(window.location.search).get("next");
      router.push(next?.startsWith("/") ? next : "/profile");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Authentication failed.");
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (next: Mode) => {
    setMode(next);
    setError(null);
    setPassword("");
  };

  return (
    <main className="auth-page">
      <section className="auth-story">
        <Link className="brand auth-brand" href="/"><span className="brand-mark"><Check size={18} strokeWidth={3} /></span><span>NiyamCart</span></Link>
        <div><span className="eyebrow"><Sparkles size={14} /> Bounded AI commerce</span><h1>Your shopping account.<br /><em>Still under your control.</em></h1><p>Save preferences and review verified test orders without giving the AI authority over money.</p></div>
        <ul><li><ShieldCheck size={17} /> Passwords are hashed server-side</li><li><LockKeyhole size={17} /> Session token stays in an HttpOnly cookie</li><li><Check size={17} /> No card, CVV, OTP, or bank details stored</li></ul>
      </section>
      <section className="auth-panel">
        <div className="auth-card">
          <div className="auth-tabs" role="tablist"><button className={mode === "login" ? "active" : ""} onClick={() => switchMode("login")} role="tab" aria-selected={mode === "login"}>Log in</button><button className={mode === "signup" ? "active" : ""} onClick={() => switchMode("signup")} role="tab" aria-selected={mode === "signup"}>Sign up</button></div>
          <header><span className="kicker">WELCOME TO NIYAMCART</span><h2>{mode === "login" ? "Good to see you again" : "Create your account"}</h2><p>{mode === "login" ? "Sign in to open your orders and profile." : "One safe account for preferences and test receipts."}</p></header>
          <form onSubmit={submit}>
            {mode === "signup" && <label><span>Name</span><input value={name} onChange={(event) => setName(event.target.value)} minLength={2} maxLength={80} autoComplete="name" placeholder="Your name" required /></label>}
            <label><span>Email</span><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" placeholder="you@example.com" required /></label>
            <label><span>Password</span><div className="password-field"><input type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} minLength={mode === "signup" ? 8 : 1} maxLength={128} autoComplete={mode === "signup" ? "new-password" : "current-password"} placeholder={mode === "signup" ? "8+ characters" : "Your password"} required /><button type="button" onClick={() => setShowPassword((shown) => !shown)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div>{mode === "signup" && <small>Use uppercase, lowercase, and at least one number.</small>}</label>
            {error && <p className="auth-error" role="alert">{error}</p>}
            <button className="auth-submit" type="submit" disabled={loading}>{loading ? "Please wait…" : mode === "login" ? "Log in securely" : "Create account"}<ArrowRight size={17} /></button>
          </form>
          <p className="auth-switch">{mode === "login" ? "New to NiyamCart?" : "Already registered?"} <button onClick={() => switchMode(mode === "login" ? "signup" : "login")}>{mode === "login" ? "Create an account" : "Log in"}</button></p>
          <small className="auth-boundary"><ShieldCheck size={13} /> Authentication never grants the agent payment permission.</small>
        </div>
      </section>
    </main>
  );
}
