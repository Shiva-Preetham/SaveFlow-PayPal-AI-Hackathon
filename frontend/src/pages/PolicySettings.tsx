import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import PolicyGrid from "../components/PolicyGrid";
import type { Compiled, PolicyResponse, Rules } from "../lib/api";
import { api } from "../lib/api";

const EXAMPLE = "Never give more than 20% off. Students who say it's too expensive should get the Lite plan instead. "
  + "Pauses only after 3 paid months, max 2 months. If someone has a problem with the app, don't make an offer — just let them go. "
  + "Give Jane from the Tuesday class a free month.";

export default function PolicySettings() {
  const [policy, setPolicy] = useState<PolicyResponse | null>(null);
  const [text, setText] = useState("");
  const [compiled, setCompiled] = useState<Compiled | null>(null);
  const [draft, setDraft] = useState<Rules | null>(null);
  const [preview, setPreview] = useState<Compiled | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const load = () => api.policy().then((p) => { setPolicy(p); setText(p.source_text ?? ""); setDraft(p.rules); setPreview(null); })
    .catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const guard = async <T,>(fn: () => Promise<T>) => {
    setBusy(true); setError(null);
    try { return await fn(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); return null; } finally { setBusy(false); }
  };

  const onGridChange = useCallback((r: Rules) => {
    setDraft(r);
    api.preview(r).then(setPreview).catch((e) => { setPreview(null); setError(e.message); });
  }, []);

  const simulate = (rules: Rules) => {
    try { sessionStorage.setItem("saveflow.simulate", JSON.stringify(rules)); } catch { /* storage blocked */ }
    navigate("/simulator");
  };

  if (!policy) return <p className="text-sm text-slate-500">{error ?? "Loading policy…"}</p>;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Retention policy <span className="text-base font-normal text-slate-500">v{policy.version}</span></h1>
        <p className="text-sm text-slate-500">The AI may only make offers this policy allows. Code enforces it on every decision.</p>
      </div>
      {error && <p className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="space-y-3 rounded-xl bg-white p-5 ring-1 ring-slate-200">
          <h2 className="font-semibold">Write your rules in plain English</h2>
          <p className="text-sm text-slate-500">The AI turns them into structured rules; code validates them; you approve a summary written by code before anything changes.</p>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={6} className="w-full rounded-md border border-slate-300 p-2 text-sm" />
          <div className="flex flex-wrap gap-2">
            <button disabled={busy || text.trim().length < 5} onClick={() => guard(() => api.compile(text)).then((c) => c && setCompiled(c))} className="btn-primary">
              {busy ? "Compiling…" : "Compile with AI"}
            </button>
            <button onClick={() => setText(EXAMPLE)} className="btn-secondary">Try an example</button>
          </div>
          {compiled && <CompiledView c={compiled} />}
          {compiled?.ok && compiled.rules && (
            <div className="flex flex-wrap gap-2">
              <button disabled={busy} onClick={() => guard(() => api.apply(compiled.rules!, text)).then((p) => { if (p) { setCompiled(null); load(); } })} className="btn-primary">
                Approve &amp; apply
              </button>
              <button onClick={() => simulate(compiled.rules!)} className="btn-secondary">Test on past cancellations first</button>
              <button onClick={() => setCompiled(null)} className="btn-secondary">Discard</button>
            </div>
          )}
        </section>

        <section className="space-y-3 rounded-xl bg-white p-5 ring-1 ring-slate-200">
          <h2 className="font-semibold">Current rules</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {policy.summary.map((s) => <li key={s}>{s}</li>)}
          </ul>
          {policy.warnings.map((w) => <p key={w} className="rounded-md bg-amber-50 p-2 text-sm text-amber-900">{w}</p>)}
          <h3 className="pt-2 text-sm font-semibold">Version history</h3>
          <ul className="space-y-1 text-sm">
            {policy.history.map((h) => (
              <li key={h.version} className="flex gap-2">
                <span className="w-10 font-mono">v{h.version}</span>
                <span className={h.status === "active" ? "text-emerald-700" : "text-slate-400"}>{h.status}</span>
                <span className="text-slate-400">{new Date(h.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className="space-y-3 rounded-xl bg-white p-5 ring-1 ring-slate-200">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="font-semibold">Edit rules directly</h2>
            <p className="text-sm text-slate-500">Click a value to edit. The server validates each change and shows what will differ.</p>
          </div>
          {draft && preview && preview.changes.length > 0 && (
            <div className="flex gap-2">
              <button onClick={() => simulate(draft)} className="btn-secondary">Simulate</button>
              <button onClick={() => { setDraft(policy.rules); setPreview(null); }} className="btn-secondary">Undo</button>
              <button disabled={busy} onClick={() => guard(() => api.apply(draft, policy.source_text ?? undefined)).then((p) => p && load())} className="btn-primary">
                Apply {preview.changes.length} change(s)
              </button>
            </div>
          )}
        </div>
        {draft && <PolicyGrid rules={draft} onChange={onGridChange} changed={preview?.changes.map((c) => c.field) ?? []} />}
        {preview && preview.changes.length > 0 && <CompiledView c={{ ...preview, ok: true, errors: [], ai_source: "manual" }} />}
      </section>
    </div>
  );
}

function CompiledView({ c }: { c: Compiled }) {
  return (
    <div className="space-y-2 rounded-lg bg-slate-50 p-3 text-sm">
      {c.errors.map((e) => <p key={e} className="text-rose-700">✗ {e}</p>)}
      {c.ok && (
        <>
          <div className="text-xs font-semibold uppercase text-slate-500">Summary (written by code, from the validated rules)</div>
          <ul className="list-disc pl-5">{c.summary.map((s) => <li key={s}>{s}</li>)}</ul>
          {c.changes.length > 0 && (
            <table className="w-full text-xs">
              <thead className="text-left text-slate-500"><tr><th>Changed</th><th>From</th><th>To</th></tr></thead>
              <tbody>
                {c.changes.map((x) => (
                  <tr key={x.field} className="border-t border-slate-200">
                    <td className="py-1 font-mono">{x.field}</td><td>{JSON.stringify(x.old)}</td><td className="font-medium">{JSON.stringify(x.new)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
      {c.warnings.map((w) => <p key={w} className="rounded bg-amber-100 p-2 text-amber-900">⚠ {w}</p>)}
      {c.ai_source !== "manual" && <p className="text-xs text-slate-400">source: {c.ai_source}</p>}
    </div>
  );
}
