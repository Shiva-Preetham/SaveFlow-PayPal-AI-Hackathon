export type Action = {
  id: string; type: "pause" | "discount" | "downgrade" | "cancel"; label: string; months: number; pct: number;
  plan_key: string | null; needs_buyer_approval: boolean; revenue_kept_12m: number;
};

export type PayPalCall = {
  method: string; path: string; status: number | string; idempotency_key?: string; debug_id?: string | null;
  error?: string; simulated?: boolean; note?: string; at: string;
};

export type AuditEntry = {
  id: number; created_at: string; action: string; subscriber_id: number | null; attempt_id: number | null;
  detail: Record<string, unknown>;
};

export type AttemptRow = {
  id: number; created_at: string; subscriber_id: number; subscriber: string; is_live: boolean; channel: string;
  reason: string; category: string | null; reason_summary: string | null; offer: string | null;
  offer_type: string | null; offer_id: string | null; needs_buyer_approval: boolean; outcome: string;
  revenue_kept_12m: number; potential_revenue_12m: number; guardrail: string; injection_suspected: boolean;
  ai_source: string; months_paid: number | null; plan: string | null; policy_version: number | null;
  is_demo_data: boolean; counter_used: boolean; paypal_call_count: number;
};

export type AttemptDetail = AttemptRow & {
  message: string | null; rationale: string | null; proposed_action_id: string | null;
  allowed_actions: Action[]; guardrail_note: string | null; context: Record<string, unknown>;
  paypal_calls: PayPalCall[]; approve_url: string | null; audit: AuditEntry[];
};

export type Subscriber = {
  id: number; name: string; plan_key: string; state: string; is_live: boolean; months_paid: number;
  failed_payments: number; offers_received: number; persona: string | null; paypal_subscription_id: string | null;
  resume_at: string | null;
};

export type Rules = {
  pause_enabled: boolean; max_pause_months: number; min_paid_months_for_pause: number; discount_enabled: boolean;
  max_discount_pct: number; min_paid_months_for_discount: number; discount_only_for: string[];
  downgrade_enabled: boolean; max_offers_per_subscriber: number; no_offer_for: string[];
  prefer: Record<string, string>;
};

export type PolicyResponse = {
  version: number; rules: Rules; source_text: string | null; summary: string[]; warnings: string[];
  history: { version: number; status: string; created_at: string; source_text: string | null }[];
};

export type Compiled = {
  ok: boolean; rules: Rules | null; summary: string[]; changes: { field: string; old: unknown; new: unknown }[];
  warnings: string[]; errors: string[]; ai_source: string;
};

export type Dashboard = {
  attempts: number; saved: number; save_rate: number; revenue_kept_12m: number; blocked_by_guardrail: number;
  injection_attempts: number; awaiting_approval: number; win_backs: number; demo_data_rows: number;
  by_reason: { category: string; attempts: number; saved: number }[];
};

export type Config = {
  paypal_client_id: string | null; pro_plan_id: string | null; currency: string; demo_mode: boolean;
  paypal_configured: boolean; gemini_configured: boolean; gemini_model: string;
  plans: { key: string; name: string; price: number }[];
};

export type SimRow = {
  attempt_id: number; subscriber: string; category: string; reason: string; months_paid: number;
  original_offer: string; original_outcome: string; simulated_offer: string; changed: boolean;
  revenue_before: number; revenue_after: number;
};
export type SimResult = {
  rows: SimRow[];
  totals: { attempts: number; changed: number; no_offer_before: number; no_offer_after: number;
    revenue_offered_before: number; revenue_offered_after: number };
};

export class ApiError extends Error {
  constructor(public status: number, message: string, public debugId?: string) { super(message); }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`/api${path}`, {
    ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!r.ok) {
    let body: { message?: string; detail?: unknown; debug_id?: string; name?: string } = {};
    try { body = await r.json(); } catch { /* not JSON */ }
    const detail = Array.isArray(body.detail) ? body.detail.map((d) => (typeof d === "string" ? d : d.msg)).join("; ")
      : typeof body.detail === "string" ? body.detail : undefined;
    const msg = body.message ?? detail ?? `Request failed (${r.status})`;
    throw new ApiError(r.status, body.name ? `PayPal: ${body.name} — ${msg}` : msg, body.debug_id);
  }
  return r.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) });

export const api = {
  health: () => request<{ status: string; paypal_configured: boolean; gemini_configured: boolean; paypal_catalogue: string }>("/health"),
  config: () => request<Config>("/config"),
  dashboard: () => request<Dashboard>("/dashboard"),
  attempts: (channel?: string) => request<AttemptRow[]>(`/attempts${channel ? `?channel=${channel}` : ""}`),
  attempt: (id: number) => request<AttemptDetail>(`/attempts/${id}`),
  audit: () => request<AuditEntry[]>("/audit"),
  subscribers: (featured = true) => request<Subscriber[]>(`/subscribers?featured=${featured}`),
  registerLive: (subscription_id: string, name: string) => post<Subscriber>("/subscribers/live", { subscription_id, name }),
  cancel: (subscriber_id: number, reason: string) => post<AttemptDetail>("/cancel", { subscriber_id, reason }),
  accept: (id: number) => post<AttemptDetail>(`/attempts/${id}/accept`),
  counter: (id: number, text: string) => post<AttemptDetail>(`/attempts/${id}/counter`, { text }),
  decline: (id: number) => post<AttemptDetail>(`/attempts/${id}/decline`),
  confirm: (id: number) => post<AttemptDetail>(`/attempts/${id}/confirm`),
  policy: () => request<PolicyResponse>("/policy"),
  compile: (text: string) => post<Compiled>("/policy/compile", { text }),
  preview: (rules: Rules) => post<Compiled & { rules: Rules }>("/policy/preview", { rules }),
  apply: (rules: Rules, source_text?: string) => post<PolicyResponse>("/policy/apply", { rules, source_text }),
  simulate: (rules: Rules) => post<SimResult>("/simulate", { rules }),
  cancelInPayPal: (subscriberId: number, event_id?: string) =>
    post<{ event_id: string; result: string; duplicate: boolean }>(`/demo/cancel-in-paypal/${subscriberId}`, { event_id }),
  resume: (subscriberId: number) => post<Subscriber>(`/demo/resume/${subscriberId}`),
  reset: () => post<{ status: string }>("/demo/reset"),
};

export const money = (n: number | null | undefined) =>
  n == null ? "" : `$${n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

export const CATEGORY_LABEL: Record<string, string> = {
  temporary: "Temporary break", price: "Price", low_usage: "Low usage", product_problem: "Product problem",
  competitor: "Competitor", other: "Other",
};
