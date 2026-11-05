import { useEffect, useRef, useState } from "react";
import type { Config } from "../lib/api";

type PayPalButtons = (opts: {
  style?: Record<string, string>;
  createSubscription: (data: unknown, actions: { subscription: { create: (o: { plan_id: string }) => Promise<string> } }) => Promise<string>;
  onApprove: (data: { subscriptionID?: string | null }) => Promise<void>;
  onError: (err: unknown) => void;
}) => { render: (el: HTMLElement) => Promise<void>; close?: () => void };

declare global {
  interface Window { paypal?: { Buttons: PayPalButtons } }
}

let sdkPromise: Promise<void> | null = null;
function loadSdk(clientId: string, currency: string): Promise<void> {
  sdkPromise ??= new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}&vault=true&intent=subscription&currency=${currency}`;
    s.onload = () => resolve();
    s.onerror = () => { sdkPromise = null; reject(new Error("Could not load the PayPal SDK")); };
    document.head.appendChild(s);
  });
  return sdkPromise;
}

/** PayPal JS SDK Subscribe button for the merchant's Pro plan. */
export default function PayPalSubscribe({ config, onSubscribed }: { config: Config | null; onSubscribed: (id: string) => Promise<void> }) {
  const ref = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<string | null>(null);
  const callback = useRef(onSubscribed);
  callback.current = onSubscribed;

  useEffect(() => {
    if (!config?.paypal_client_id || !config.pro_plan_id || !ref.current) return;
    let closed = false;
    const el = ref.current;
    loadSdk(config.paypal_client_id, config.currency).then(() => {
      if (closed || !window.paypal) return;
      el.innerHTML = "";
      window.paypal.Buttons({
        style: { shape: "rect", color: "gold", layout: "vertical", label: "subscribe" },
        createSubscription: (_d, actions) => actions.subscription.create({ plan_id: config.pro_plan_id! }),
        onApprove: async (data) => {
          if (!data.subscriptionID) return;
          setStatus("Subscribed. Registering with SaveFlow…");
          try { await callback.current(data.subscriptionID); setStatus(`Live subscription ${data.subscriptionID} added.`); }
          catch (e) { setStatus(e instanceof Error ? e.message : "Could not register the subscription"); }
        },
        onError: () => setStatus("PayPal reported an error. Use a US sandbox Personal account."),
      }).render(el).catch(() => setStatus("Could not render the PayPal button"));
    }).catch((e) => setStatus(e.message));
    return () => { closed = true; };
  }, [config]);

  if (!config) return <p className="text-xs text-slate-500">Loading…</p>;
  if (!config.paypal_client_id) return <p className="text-xs text-slate-500">PayPal keys are not configured on this server, so only simulated subscribers are available.</p>;
  if (!config.pro_plan_id) return <p className="text-xs text-slate-500">PayPal plans are still syncing — refresh in a few seconds.</p>;
  return (
    <div>
      <p className="mb-2 text-xs text-slate-500">Yoga Pro, $10/month. Log in with the sandbox buyer from the README.</p>
      <div ref={ref} />
      {status && <p className="mt-2 text-xs text-slate-700">{status}</p>}
    </div>
  );
}
