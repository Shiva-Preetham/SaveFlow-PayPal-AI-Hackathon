import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import AuditLog from "./pages/AuditLog";
import CancelFlow from "./pages/CancelFlow";
import Dashboard from "./pages/Dashboard";
import PolicySettings from "./pages/PolicySettings";

type Health = { status: string; paypal_configured: boolean; gemini_configured: boolean };

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/policy", label: "Policy" },
  { to: "/audit", label: "Audit log" },
  { to: "/cancel", label: "Cancel flow (subscriber)" },
];

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [backendDown, setBackendDown] = useState(false);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setHealth)
      .catch(() => setBackendDown(true));
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="flex flex-wrap items-center gap-6 border-b bg-white px-6 py-3">
        <span className="text-lg font-semibold">SaveFlow</span>
        <nav className="flex flex-wrap gap-4 text-sm">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end
              className={({ isActive }) => (isActive ? "font-medium text-blue-700" : "text-slate-600 hover:text-slate-900")}>
              {l.label}
            </NavLink>
          ))}
        </nav>
        <span className="ml-auto text-xs text-slate-500">
          {backendDown ? "Backend not reachable (it may be waking up)" :
            health ? `PayPal ${health.paypal_configured ? "✓" : "✗"} · Gemini ${health.gemini_configured ? "✓" : "✗"}` : "Connecting…"}
        </span>
      </header>
      <main className="p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/policy" element={<PolicySettings />} />
          <Route path="/audit" element={<AuditLog />} />
          <Route path="/cancel" element={<CancelFlow />} />
        </Routes>
      </main>
    </div>
  );
}
