import type { ColDef } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import AttemptWork from "../components/AttemptWork";
import { MoneyCell, OutcomeCell, SubscriberCell, gridTheme } from "../components/grid";
import type { AttemptDetail, AttemptRow, Subscriber } from "../lib/api";
import { api } from "../lib/api";

export default function WinBacks() {
  const [rows, setRows] = useState<AttemptRow[]>([]);
  const [subs, setSubs] = useState<Subscriber[]>([]);
  const [pick, setPick] = useState<number | "">("");
  const [log, setLog] = useState<{ event_id: string; result: string; duplicate: boolean }[]>([]);
  const [selected, setSelected] = useState<AttemptDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.attempts("win_back").then(setRows).catch((e) => setError(e.message));
    api.subscribers().then((s) => setSubs(s.filter((x) => x.state !== "CANCELLED"))).catch(() => undefined);
  }, []);
  useEffect(load, [load]);

  const fire = async (eventId?: string) => {
    if (pick === "") return;
    setError(null);
    try { const r = await api.cancelInPayPal(pick, eventId); setLog((l) => [r, ...l]); load(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  const cols = useMemo<ColDef<AttemptRow>[]>(() => [
    { field: "created_at", headerName: "When", width: 170, valueFormatter: (p) => new Date(p.value).toLocaleString() },
    { field: "subscriber", width: 180, cellRenderer: SubscriberCell },
    { field: "months_paid", headerName: "Months paid", width: 120 },
    { field: "offer", headerName: "Come-back offer", flex: 1 },
    { field: "outcome", width: 170, cellRenderer: OutcomeCell },
    { field: "potential_revenue_12m", headerName: "Value if accepted", width: 150, cellRenderer: MoneyCell },
  ], []);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Win-backs</h1>
        <p className="text-sm text-slate-500">
          Subscribers can cancel inside PayPal and never see the save page. PayPal then sends
          <code className="mx-1 rounded bg-slate-100 px-1">BILLING.SUBSCRIPTION.CANCELLED</code>; SaveFlow verifies it,
          ignores duplicates by event id, re-reads the subscription from PayPal, and prepares one personalised come-back offer.
        </p>
      </div>
      {error && <p className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}

      <section className="space-y-3 rounded-xl bg-white p-5 ring-1 ring-slate-200">
        <h2 className="font-semibold">Demo: a subscriber cancels inside PayPal</h2>
        <p className="text-sm text-slate-500">Sends the event through the same handler as real webhooks. Only signature verification is skipped, and the event is stored as <b>SIMULATED</b>. For a live subscriber the subscription is really cancelled in PayPal first.</p>
        <div className="flex flex-wrap items-center gap-2">
          <select value={pick} onChange={(e) => setPick(e.target.value ? Number(e.target.value) : "")} className="rounded-md border border-slate-300 px-2 py-1.5 text-sm">
            <option value="">Choose a subscriber…</option>
            {subs.map((s) => <option key={s.id} value={s.id}>{s.name}{s.is_live ? " (PayPal live)" : ""} · {s.months_paid} months</option>)}
          </select>
          <button disabled={pick === ""} onClick={() => fire()} className="btn-primary">Send CANCELLED webhook</button>
          <button disabled={pick === "" || !log[0]} onClick={() => fire(log[0]?.event_id)} className="btn-secondary">Re-send the same event (duplicate)</button>
        </div>
        {log.length > 0 && (
          <ul className="space-y-1 font-mono text-xs">
            {log.map((l, i) => (
              <li key={i} className={l.duplicate ? "text-amber-700" : "text-emerald-700"}>{l.event_id} → {l.result}</li>
            ))}
          </ul>
        )}
      </section>

      <div style={{ height: 360 }}>
        <AgGridReact<AttemptRow> theme={gridTheme} rowData={rows} columnDefs={cols}
          defaultColDef={{ sortable: true, filter: true, resizable: true }}
          overlayNoRowsTemplate="No win-backs yet: send a CANCELLED webhook above."
          onRowClicked={(e) => e.data && api.attempt(e.data.id).then(setSelected)} />
      </div>
      {selected && (
        <div className="rounded-xl bg-white p-5 ring-1 ring-slate-200">
          <div className="mb-3 flex justify-between"><h2 className="font-semibold">{selected.subscriber}: win-back #{selected.id}</h2>
            <button onClick={() => setSelected(null)} className="btn-secondary">Close</button></div>
          <AttemptWork a={selected} />
        </div>
      )}
    </div>
  );
}
