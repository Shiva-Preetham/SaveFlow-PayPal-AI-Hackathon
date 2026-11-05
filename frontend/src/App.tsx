import { useEffect, useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./lib/api";
import Approved from "./pages/Approved";
import AuditLog from "./pages/AuditLog";
import CancelFlow from "./pages/CancelFlow";
import Dashboard from "./pages/Dashboard";
import PolicySettings from "./pages/PolicySettings";
import Simulator from "./pages/Simulator";
import WinBacks from "./pages/WinBacks";

type Health = { status: string; paypal_configured: boolean; gemini_configured: boolean; paypal_catalogue: string };

const links = [
  { to: "/", label: "Workspace" },
  { to: "/try", label: "Try it as a subscriber" },
  { to: "/policy", label: "Policy" },
  { to: "/simulator", label: "What-if simulator" },
  { to: "/win-backs", label: "Win-backs" },
  { to: "/audit", label: "Audit log" },
];

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [waking, setWaking] = useState(0);
  const location = useLocation();

  // Render's free tier sleeps when idle; keep retrying while it wakes up.
  useEffect(() => {
    let stop = false;
    const ping = () => api.health().then((h) => !stop && setHealth(h)).catch(() => {
      if (stop) return;
      setWaking((n) => n + 1);
      window.setTimeout(ping, 3000);
    });
    ping();
    return () => { stop = true; };
  }, []);

  if (location.pathname === "/approved") return <Approved />;
  if (!health) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
        <div className="max-w-md rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-slate-200">
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-teal-600 border-t-transparent" />
          <h1 className="text-lg font-semibold">Waking up SaveFlow…</h1>
          <p className="mt-2 text-sm text-slate-500">
            The demo runs on a free server that sleeps when idle. The first load can take 30–60 seconds{waking > 0 ? ` (attempt ${waking + 1})` : ""}.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-30 border-b bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1500px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 md:px-6">
          <span className="flex items-center gap-2 text-lg font-semibold">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-teal-700 text-sm text-white">S</span>
            SaveFlow
          </span>
          <nav className="flex flex-wrap gap-1 text-sm">
            {links.map((l) => (
              <NavLink key={l.to} to={l.to} end
                className={({ isActive }) => `rounded-md px-2.5 py-1.5 ${isActive ? "bg-teal-50 font-medium text-teal-800" : "text-slate-600 hover:bg-slate-100"}`}>
                {l.label}
              </NavLink>
            ))}
          </nav>
          <span className="ml-auto flex items-center gap-3 text-xs text-slate-500">
            <Status ok={health.paypal_configured} label="PayPal sandbox" title={health.paypal_catalogue} />
            <Status ok={health.gemini_configured} label="Gemini" title={health.gemini_configured ? "" : "No API key: rule-based fallback and cached answers only"} />
            <button onClick={() => { if (confirm("Reset all demo data?")) api.reset().then(() => window.location.reload()); }}
              className="rounded border border-slate-200 px-2 py-1 hover:bg-slate-50">Reset demo</button>
          </span>
        </div>
      </header>
      <main className="mx-auto max-w-[1500px] p-4 md:p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/try" element={<CancelFlow />} />
          <Route path="/policy" element={<PolicySettings />} />
          <Route path="/simulator" element={<Simulator />} />
          <Route path="/win-backs" element={<WinBacks />} />
          <Route path="/audit" element={<AuditLog />} />
          <Route path="*" element={<Dashboard />} />
        </Routes>
      </main>
      <footer className="mx-auto max-w-[1500px] px-6 pb-8 text-xs text-slate-400">
        SaveFlow demo · PayPal sandbox only, no real money moves · “Sunrise Yoga Studio” is a made-up merchant
      </footer>
    </div>
  );
}

function Status({ ok, label, title }: { ok: boolean; label: string; title?: string }) {
  return (
    <span title={title} className="flex items-center gap-1">
      <span className={`h-2 w-2 rounded-full ${ok ? "bg-emerald-500" : "bg-slate-300"}`} />{label}
    </span>
  );
}
