"use client";

import { Check, CreditCard, Languages, LogOut, MessageCircle, Save, ShieldCheck, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { emptyProfile, loadCustomerProfile, saveCustomerProfile, type CustomerProfile } from "@/lib/customer";
import { getCurrentUser, logout, type AuthUser } from "@/lib/auth";

const languages = ["English", "हिन्दी", "বাংলা", "ગુજરાતી", "ಕನ್ನಡ", "മലയാളം", "मराठी", "ଓଡ଼ିଆ", "ਪੰਜਾਬੀ", "தமிழ்", "తెలుగు"];

export function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<CustomerProfile>(emptyProfile);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    void getCurrentUser()
      .then(({ user: authenticated }) => {
        setUser(authenticated);
        const stored = loadCustomerProfile();
        setProfile({ ...stored, name: stored.name || authenticated.name, email: authenticated.email });
        setReady(true);
      })
      .catch(() => router.replace("/auth?next=/profile"));
  }, [router]);

  const update = <K extends keyof CustomerProfile>(key: K, value: CustomerProfile[K]) => {
    setProfile((current) => ({ ...current, [key]: value }));
    setSaved(false);
  };
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    saveCustomerProfile(profile);
    setSaved(true);
  };

  const signOut = async () => {
    await logout().catch(() => undefined);
    router.replace("/auth");
    router.refresh();
  };

  if (!user) return <div className="orders-loading"><ShieldCheck size={20} /> Checking your secure session…</div>;

  return (
    <>
      <section className="account-hero">
        <div><span className="kicker">YOUR ACCOUNT</span><h1>Profile</h1><p>Keep your shopping preferences in one place. This MVP stores them only in this browser and never stores payment credentials.</p></div>
        <div className="profile-account"><div className="profile-avatar"><UserRound size={31} /><span>{profile.name ? profile.name.charAt(0).toUpperCase() : "N"}</span></div><button onClick={() => void signOut()}><LogOut size={15} /> Log out</button></div>
      </section>
      <section className="profile-grid">
        <form className="profile-form" onSubmit={submit}>
          <header><div><UserRound size={19} /><span><b>Personal details</b><small>Used to personalize the storefront on this device</small></span></div></header>
          <div className="profile-fields">
            <label><span>Display name</span><input value={profile.name} onChange={(event) => update("name", event.target.value)} placeholder="Your name" autoComplete="name" disabled={!ready} /></label>
            <label><span>Account email</span><input type="email" value={profile.email} readOnly autoComplete="email" disabled={!ready} title="Your sign-in email cannot be changed from the MVP profile" /></label>
            <label><span>Phone</span><input type="tel" value={profile.phone} onChange={(event) => update("phone", event.target.value)} placeholder="+91 98765 43210" autoComplete="tel" disabled={!ready} /></label>
            <label><span>Preferred shopping language</span><select value={profile.preferredLanguage} onChange={(event) => update("preferredLanguage", event.target.value)} disabled={!ready}>{languages.map((language) => <option key={language}>{language}</option>)}</select></label>
          </div>
          <label className="profile-consent"><input type="checkbox" checked={profile.whatsappOptIn} onChange={(event) => update("whatsappOptIn", event.target.checked)} /><MessageCircle size={17} /><span><b>Prefer WhatsApp order updates</b><small>You will still confirm the exact destination during checkout.</small></span></label>
          <div className="profile-save"><button type="submit" disabled={!ready}><Save size={16} /> Save profile</button>{saved && <span role="status"><Check size={14} /> Saved in this browser</span>}</div>
        </form>
        <aside className="profile-safety">
          <h2>Account boundaries</h2>
          <div><Languages size={19} /><span><b>11 supported languages</b><small>Niyam can answer in the language you speak or type.</small></span></div>
          <div><CreditCard size={19} /><span><b>No saved payment methods</b><small>Card, CVV, OTP, and banking details stay outside NiyamCart.</small></span></div>
          <div><ShieldCheck size={19} /><span><b>You remain the payment authority</b><small>No profile preference can approve a cart or payment.</small></span></div>
          <p><ShieldCheck size={14} /> Profile data remains on this device for the MVP and is not sent to the agent.</p>
        </aside>
      </section>
    </>
  );
}
