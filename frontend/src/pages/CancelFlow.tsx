import { useCallback, useEffect, useRef, useState } from "react";
import AttemptWork from "../components/AttemptWork";
import { Pill } from "../components/grid";
import PayPalSubscribe from "../components/PayPalSubscribe";
import type { AttemptDetail, Config, Subscriber } from "../lib/api";
import { api, money } from "../lib/api";

const suggested = (persona: string | null) => persona?.match(/"([^"]+)"/)?.[1] ?? "";

export default function CancelFlow() {
  const [subs, setSubs] = useState<Subscriber[]>([]);
  const [config, setConfig] = useState<Config | null>(null);
  const [sub, setSub] = useState<Subscriber | null>(null);
  const [reason, setReason] = useState("");
  const [attempt, setAttempt] = useState<AttemptDetail | null>(null);
  const [counterText, setCounterText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const poll = useRef<number | null>(null);

  const loadSubs = useCallback(() => api.subscribers().then(setSubs).catch((e) => setError(e.message)), []);
  useEffect(() => { loadSubs(); api.config().then(setConfig).catch(() => undefined); }, [loadSubs]);

  const stopPolling = () => { if (poll.current) window.clearInterval(poll.current); poll.current = null; };
  useEffect(() => stopPolling, []);

  // The approval popup reports back via postMessage; polling PayPal through /confirm is the backup.
  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (e.origin === window.location.origin && e.data?.type === "saveflow-approved" && attempt && e.data.attempt === attempt.id) {
        api.confirm(attempt.id).then((a) => { setAttempt(a); if (a.outcome !== "awaiting_approval") stopPolling(); loadSubs(); });
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [attempt, loadSubs]);

  const run = async (fn: () => Promise<AttemptDetail>) => {
    setBusy(true); setError(null);
    try { const a = await fn(); setAttempt(a); loadSubs(); return a; }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); return null; }
    finally { setBusy(false); }
  };

  const choose = (s: Subscriber) => { setSub(s); setAttempt(null); setReason(suggested(s.persona)); setCounterText(""); setError(null); stopPolling(); };

  const accept = async () => {
    if (!attempt) return;
    // Open the popup inside the click (so it isn't blocked), then point it at PayPal once we have the link.
    const popup = attempt.needs_buyer_approval && attempt.is_live ? window.open("about:blank", "paypal-approve", "width=520,height=720") : null;
    const a = await run(() => api.accept(attempt.id));
    if (popup) {
      if (a?.approve_url) {
        popup.location.href = a.approve_url;
        stopPolling();
        poll.current = window.setInterval(() => {
          api.confirm(a.id).then((x) => { if (x.outcome !== "awaiting_approval") { setAttempt(x); stopPolling(); loadSubs(); } });
        }, 4000);
      } else popup.close();
    }
  };

  const outcome = attempt?.outcome;
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Try it as a subscriber</h1>
        <p className="text-sm text-slate-500">
          Pick a demo subscriber (PayPal calls are simulated and labelled) or subscribe with a <b>PayPal sandbox</b> buyer
          to make every action a real PayPal API call. The right panel shows what the merchant sees.
        </p>
      </div>
      {error && <p className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}

      <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)_minmax(0,1.1fr)]">
        {/* Subscriber picker */}
        <div className="space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Subscribers</h2>
          {subs.map((s) => (
            <button key={s.id} onClick={() => choose(s)}
              className={`w-full rounded-lg bg-white p-3 text-left text-sm ring-1 transition ${sub?.id === s.id ? "ring-2 ring-teal-600" : "ring-slate-200 hover:ring-slate-300"}`}>
              <div className="flex items-center justify-between">
                <span className="font-medium">{s.name}</span>
                <span className="flex gap-1">
                  {s.is_live && <Pill className="bg-[#003087] text-white">PayPal live</Pill>}
                  <Pill className={s.state === "ACTIVE" ? "bg-emerald-100 text-emerald-800" : s.state === "CANCELLED" ? "bg-rose-100 text-rose-800" : "bg-amber-100 text-amber-800"}>{s.state}</Pill>
                </span>
              </div>
              <div className="mt-1 text-xs text-slate-500">{s.plan_key} · {s.months_paid} month{s.months_paid === 1 ? "" : "s"} paid{s.offers_received ? ` · ${s.offers_received} offer used` : ""}</div>
              {s.persona && <div className="mt-1 text-xs text-slate-600">{s.persona}</div>}
            </button>
          ))}
          <div className="rounded-lg bg-white p-3 ring-1 ring-slate-200">
            <div className="mb-2 text-sm font-medium">Subscribe for real (PayPal sandbox)</div>
            <PayPalSubscribe config={config} onSubscribed={async (id) => {
              const s = await api.registerLive(id, "Sandbox buyer");
              await loadSubs(); choose(s);
            }} />
          </div>
        </div>

        {/* What the subscriber sees */}
        <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <div className="mb-4 flex items-center gap-2 border-b pb-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-orange-400 text-sm font-bold text-white">☀</div>
            <div>
              <div className="font-semibold">Sunrise Yoga Studio</div>
              <div className="text-xs text-slate-500">Manage membership</div>
            </div>
          </div>
          {!sub && <p className="text-sm text-slate-500">Choose a subscriber on the left to start.</p>}
          {sub && !attempt && (
            <form onSubmit={(e) => { e.preventDefault(); run(() => api.cancel(sub.id, reason)); }} className="space-y-3">
              <h2 className="text-lg font-semibold">Cancel your membership</h2>
              <p className="text-sm text-slate-600">Hi {sub.name.split(" ")[0]}, we're sorry to see you go. Mind telling us why, in your own words?</p>
              <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={4} required maxLength={1500}
                className="w-full rounded-md border border-slate-300 p-2 text-sm" placeholder="Any language is fine" />
              <button disabled={busy || !reason.trim() || sub.state === "CANCELLED"} className="btn-primary w-full">
                {busy ? "Thinking…" : "Continue to cancel"}
              </button>
              {sub.state === "CANCELLED" && <p className="text-xs text-rose-700">This subscription is already cancelled.</p>}
            </form>
          )}
          {attempt && (
            <div className="space-y-4">
              <p className="whitespace-pre-line text-[15px] leading-relaxed">{attempt.message}</p>
              {attempt.offer_type !== "cancel" && outcome === "offered" && (
                <div className="rounded-xl bg-teal-50 p-4 ring-1 ring-teal-200">
                  <div className="text-sm font-semibold text-teal-900">{attempt.offer}</div>
                  {attempt.needs_buyer_approval && <div className="text-xs text-teal-800">You'll confirm the new price in PayPal.</div>}
                  <button onClick={accept} disabled={busy} className="btn-primary mt-3 w-full">Accept offer</button>
                </div>
              )}
              {outcome === "offered" && !attempt.counter_used && attempt.offer_type !== "cancel" && (
                <form onSubmit={(e) => { e.preventDefault(); run(() => api.counter(attempt.id, counterText)); }} className="flex gap-2">
                  <input value={counterText} onChange={(e) => setCounterText(e.target.value)} placeholder='e.g. "Can you do 50%?"'
                    className="flex-1 rounded-md border border-slate-300 px-2 py-1.5 text-sm" />
                  <button disabled={busy || !counterText.trim()} className="btn-secondary">Ask</button>
                </form>
              )}
              {(outcome === "offered" || outcome === "no_offer") && (
                <button onClick={() => run(() => api.decline(attempt.id))} disabled={busy}
                  className="w-full text-sm text-slate-500 underline hover:text-slate-800">
                  No thanks, cancel my membership
                </button>
              )}
              {outcome === "awaiting_approval" && (
                <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
                  Waiting for you to approve in the PayPal window… {attempt.approve_url && <a className="underline" href={attempt.approve_url} target="paypal-approve">Reopen PayPal</a>}
                </div>
              )}
              {outcome === "saved" && (
                <div className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-900">
                  Done: <b>{attempt.offer}</b>. {attempt.is_live ? "Applied in PayPal." : "Applied (simulated PayPal)."} Est. {money(attempt.revenue_kept_12m)} kept over 12 months.
                </div>
              )}
              {outcome === "cancelled" && <div className="rounded-lg bg-slate-100 p-3 text-sm">Your membership is cancelled. You're welcome back anytime.</div>}
              {(outcome === "saved" || outcome === "cancelled") && (
                <button onClick={() => sub && choose(subs.find((s) => s.id === sub.id) ?? sub)} className="btn-secondary w-full">Start over</button>
              )}
              {outcome === "saved" && attempt.offer_type === "pause" && sub && (
                <button onClick={() => api.resume(sub.id).then(loadSubs).catch((e) => setError(e.message))} className="w-full text-xs text-slate-500 underline">
                  Demo: skip ahead to the end of the pause (scheduled resume)
                </button>
              )}
            </div>
          )}
        </div>

        {/* What the merchant sees */}
        <div className="rounded-2xl bg-slate-50 p-5 ring-1 ring-slate-200">
          <h2 className="mb-3 text-sm font-semibold">Behind the scenes <span className="font-normal text-slate-500">(merchant view)</span></h2>
          {attempt ? <AttemptWork a={attempt} /> : <p className="text-sm text-slate-500">The agent's work appears here.</p>}
        </div>
      </div>
    </div>
  );
}
