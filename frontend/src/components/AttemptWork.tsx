import type { AttemptDetail } from "../lib/api";
import { CATEGORY_LABEL, money } from "../lib/api";
import { Pill } from "./grid";

/** "Show its work": what the agent read, what it could choose from, what it chose, what code allowed,
 * and the exact PayPal calls. Used in the dashboard drawer and beside the subscriber cancel flow. */
export default function AttemptWork({ a }: { a: AttemptDetail }) {
  const ctx = a.context ?? {};
  return (
    <div className="space-y-5 text-sm">
      <Section title="1 · Subscriber reason">
        <p className="rounded-md bg-slate-50 p-2 italic text-slate-700">“{a.reason}”</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {a.category && <Pill className="bg-slate-800 text-white">{CATEGORY_LABEL[a.category] ?? a.category}</Pill>}
          {a.reason_summary && <span className="text-slate-500">{a.reason_summary}</span>}
          {a.injection_suspected && <Pill className="bg-amber-500 text-white">Prompt injection suspected</Pill>}
        </div>
      </Section>

      <Section title="2 · What the agent read from PayPal">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
          {Object.entries(ctx).filter(([k]) => !["state", "offers_received"].includes(k)).map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-slate-500">{k.replace(/_/g, " ")}</dt>
              <dd className="truncate font-medium">{String(v ?? "—")}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section title="3 · Offers the merchant's policy allows (computed by code)">
        <ul className="space-y-1">
          {a.allowed_actions.map((x) => (
            <li key={x.id} className={`flex items-center justify-between rounded px-2 py-1 ${x.id === a.offer_id ? "bg-teal-50 ring-1 ring-teal-500" : ""}`}>
              <span>
                <code className="mr-2 text-xs text-slate-500">{x.id}</code>{x.label}
                {x.needs_buyer_approval && <span className="ml-2 text-xs text-amber-700">(buyer approves in PayPal)</span>}
              </span>
              <span className="text-xs text-slate-500">{x.revenue_kept_12m ? `${money(x.revenue_kept_12m)}/12 mo` : ""}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="4 · Decision and guardrail">
        <div className="flex flex-wrap items-center gap-2">
          <span>AI proposed <code className="rounded bg-slate-100 px-1">{a.proposed_action_id ?? "—"}</code></span>
          <span>→ offered <code className="rounded bg-teal-100 px-1">{a.offer_id}</code></span>
          {a.guardrail === "passed" && <Pill className="bg-emerald-100 text-emerald-800">Guardrail passed</Pill>}
          {a.guardrail === "blocked" && <Pill className="bg-rose-600 text-white">Blocked by guardrail</Pill>}
          {a.guardrail === "fallback" && <Pill className="bg-slate-200 text-slate-700">AI unavailable: rule-based fallback</Pill>}
          <span className="text-xs text-slate-400">source: {a.ai_source}</span>
        </div>
        {a.guardrail_note && <p className="mt-2 rounded-md bg-rose-50 p-2 text-rose-800">{a.guardrail_note}</p>}
        {a.rationale && <p className="mt-2 text-slate-600"><span className="font-medium">Why: </span>{a.rationale}</p>}
        {a.message && <p className="mt-2 rounded-md border border-slate-200 p-2"><span className="font-medium">Message sent: </span>{a.message}</p>}
      </Section>

      <Section title={`5 · PayPal API calls (${a.paypal_calls.length})`}>
        {a.paypal_calls.length === 0 ? <p className="text-slate-400">None yet.</p> : (
          <table className="w-full text-xs">
            <thead className="text-left text-slate-500">
              <tr><th className="py-1">Call</th><th>Status</th><th>debug_id / idempotency key</th></tr>
            </thead>
            <tbody>
              {a.paypal_calls.map((c, i) => (
                <tr key={i} className="border-t border-slate-100 align-top">
                  <td className="py-1 pr-2 font-mono">{c.method} {c.path}</td>
                  <td className="pr-2">
                    {c.simulated ? <Pill className="bg-slate-100 text-slate-600" title={c.note}>simulated</Pill>
                      : <Pill className={Number(c.status) < 400 ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"}>{String(c.status)}</Pill>}
                  </td>
                  <td className="break-all font-mono text-slate-500">{c.debug_id ?? ""}{c.idempotency_key ? ` · ${c.idempotency_key}` : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      {a.audit.length > 0 && (
        <Section title="6 · Audit trail">
          <ol className="space-y-1 text-xs">
            {a.audit.map((e) => (
              <li key={e.id}><span className="text-slate-400">{new Date(e.created_at).toLocaleTimeString()}</span> <span className="font-medium">{e.action}</span></li>
            ))}
          </ol>
        </Section>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      {children}
    </section>
  );
}
