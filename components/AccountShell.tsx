import { Check, Package, ShieldCheck, UserRound } from "lucide-react";
import Link from "next/link";

export function AccountShell({ active, children }: { active: "orders" | "profile" | "journey"; children: React.ReactNode }) {
  return (
    <div className="account-shell">
      <header className="site-header account-site-header">
        <Link className="brand" href="/" aria-label="NiyamCart home">
          <span className="brand-mark"><Check size={18} strokeWidth={3} /></span>
          <span>NiyamCart</span>
        </Link>
        <nav className="desktop-nav" aria-label="Account navigation">
          <Link href="/">Shop</Link>
          <Link className={active === "journey" ? "active" : ""} href="/journey">My journey</Link>
          <Link className={active === "orders" ? "active" : ""} href="/orders">My orders</Link>
          <Link className={active === "profile" ? "active" : ""} href="/profile">Profile</Link>
        </nav>
        <div className="account-header-actions">
          <Link className={active === "journey" ? "selected" : ""} href="/journey" aria-label="My shopping journey">Journey</Link>
          <Link className={active === "orders" ? "selected" : ""} href="/orders" aria-label="My orders"><Package size={18} /><span>Orders</span></Link>
          <Link className={active === "profile" ? "selected" : ""} href="/profile" aria-label="Profile"><UserRound size={18} /><span>Profile</span></Link>
        </div>
      </header>
      <main className="account-main">
        {children}
      </main>
      <footer className="account-footer"><ShieldCheck size={14} /> NiyamCart never stores card numbers, CVV, or banking credentials.</footer>
    </div>
  );
}
