import type { ColDef, GridApi, IRowNode } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AttemptWork from "../components/AttemptWork";
import { CategoryCell, GuardrailCell, MoneyCell, OutcomeCell, SourceCell, SubscriberCell, gridTheme } from "../components/grid";
import type { AttemptDetail, AttemptRow, Dashboard as Stats } from "../lib/api";
import { CATEGORY_LABEL, api, money } from "../lib/api";

type View = { key: string; label: string; test: (r: AttemptRow) => boolean };
const VIEWS: View[] = [
  { key: "all", label: "All attempts", test: () => true },
  { key: "saved", label: "Saved", test: (r) => r.outcome === "saved" },
  { key: "attention", label: "Needs attention", test: (r) => ["awaiting_approval", "offered"].includes(r.outcome) },
  { key: "guardrail", label: "Guardrail & injections", test: (r) => r.guardrail === "blocked" || r.injection_suspected },
  { key: "live", label: "Live PayPal", test: (r) => r.is_live },
  { key: "lost", label: "Lost", test: (r) => ["cancelled", "declined"].includes(r.outcome) },
];
const LAYOUT_KEY = "saveflow.dashboard.columns";

export default function Dashboard() {
  const [rows, setRows] = useState<AttemptRow[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [quick, setQuick] = useState("");
  const [view, setView] = useState<View>(VIEWS[0]);
  const [selected, setSelected] = useState<AttemptDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const gridApi = useRef<GridApi<AttemptRow> | null>(null);

  const load = useCallback(() => {
    Promise.all([api.attempts("save_page"), api.dashboard()])
      .then(([r, s]) => { setRows(r); setStats(s); })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);
  useEffect(() => { gridApi.current?.onFilterChanged(); }, [view]);

  const columns = useMemo<ColDef<AttemptRow>[]>(() => [
    { field: "created_at", headerName: "When", width: 130, sort: "desc",
      valueFormatter: (p) => new Date(p.value).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) },
    { field: "subscriber", width: 170, cellRenderer: SubscriberCell },
    { field: "reason", flex: 2, minWidth: 220, tooltipField: "reason" },
    { field: "category", headerName: "Reason type", width: 150, cellRenderer: CategoryCell,
      filterValueGetter: (p) => CATEGORY_LABEL[p.data?.category ?? ""] ?? "" },
    { field: "months_paid", headerName: "Months paid", width: 115, filter: "agNumberColumnFilter", type: "rightAligned" },
    { field: "offer", headerName: "Offer", flex: 1, minWidth: 170 },
    { field: "outcome", width: 190, cellRenderer: OutcomeCell },
    { field: "revenue_kept_12m", headerName: "Kept (12 mo)", width: 125, cellRenderer: MoneyCell,
      filter: "agNumberColumnFilter", type: "rightAligned" },
    { field: "guardrail", width: 170, cellRenderer: GuardrailCell },
    { field: "ai_source", headerName: "Decided by", width: 140, cellRenderer: SourceCell },
    { field: "paypal_call_count", headerName: "PayPal calls", width: 115, type: "rightAligned", hide: true },
    { field: "policy_version", headerName: "Policy v", width: 95, hide: true },
  ], []);

  const onRowClicked = (id: number) => api.attempt(id).then(setSelected).catch((e) => setError(e.message));
  const saveLayout = () => {
    try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(gridApi.current?.getColumnState())); } catch { /* storage blocked */ }
  };
  const resetLayout = () => {
    try { localStorage.removeItem(LAYOUT_KEY); } catch { /* storage blocked */ }
    gridApi.current?.resetColumnState();
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Retention workspace</h1>
          <p className="text-sm text-slate-500">Sunrise Yoga Studio · every cancel attempt, what the agent offered, and what happened in PayPal</p>
        </div>
        {stats && stats.demo_data_rows > 0 && (
          <span className="rounded-md bg-amber-50 px-3 py-1.5 text-xs text-amber-800 ring-1 ring-amber-200">
            {stats.demo_data_rows} of {stats.attempts} rows are seeded demo data (labelled “Demo data”)
          </span>
        )}
      </div>
      {error && <p className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}

      {stats && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <Kpi label="Cancel attempts" value={String(stats.attempts)} />
          <Kpi label="Saved" value={`${stats.saved} · ${(stats.save_rate * 100).toFixed(0)}%`} hint="Industry benchmark ≈15%" />
          <Kpi label="Revenue kept (12-mo est.)" value={money(stats.revenue_kept_12m)} hint="If saved subscribers stay a year" />
          <Kpi label="Blocked by guardrail" value={String(stats.blocked_by_guardrail)} hint="AI picks replaced by code" />
          <Kpi label="Injection attempts" value={String(stats.injection_attempts)} hint="Flagged, policy still enforced" />
        </div>
      )}

      {stats && <Reasons stats={stats} />}

      <div className="flex flex-wrap items-center gap-2">
        {VIEWS.map((v) => (
          <button key={v.key} onClick={() => setView(v)}
            className={`rounded-full px-3 py-1 text-sm ${view.key === v.key ? "bg-teal-700 text-white" : "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"}`}>
            {v.label}
          </button>
        ))}
        <input value={quick} onChange={(e) => setQuick(e.target.value)} placeholder="Search reasons, names, offers…"
          className="ml-auto w-64 rounded-md border border-slate-300 px-3 py-1.5 text-sm" />
        <button onClick={saveLayout} className="btn-secondary">Save column layout</button>
        <button onClick={resetLayout} className="btn-secondary">Reset</button>
        <button onClick={() => gridApi.current?.exportDataAsCsv({ fileName: "saveflow-cancel-attempts.csv" })} className="btn-secondary">Export CSV</button>
        <button onClick={load} className="btn-secondary">Refresh</button>
      </div>

      <div style={{ height: 520 }}>
        <AgGridReact<AttemptRow>
          theme={gridTheme} rowData={rows} columnDefs={columns} getRowId={(p) => String(p.data.id)}
          defaultColDef={{ sortable: true, filter: true, resizable: true }}
          quickFilterText={quick} tooltipShowDelay={300} pagination paginationPageSize={50}
          isExternalFilterPresent={() => view.key !== "all"}
          doesExternalFilterPass={(n: IRowNode<AttemptRow>) => (n.data ? view.test(n.data) : true)}
          rowClassRules={{ "!bg-rose-50": (p) => p.data?.guardrail === "blocked" }}
          onGridReady={(e) => {
            gridApi.current = e.api;
            try {
              const saved = localStorage.getItem(LAYOUT_KEY);
              if (saved) e.api.applyColumnState({ state: JSON.parse(saved), applyOrder: true });
            } catch { /* storage blocked */ }
          }}
          onRowClicked={(e) => e.data && onRowClicked(e.data.id)}
        />
      </div>
      <p className="text-xs text-slate-500">Click a row to see the agent's work: the PayPal history it read, the offers the policy allowed, the guardrail check and every PayPal API call.</p>

      {selected && (
        <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/30" onClick={() => setSelected(null)}>
          <aside className="h-full w-full max-w-xl overflow-y-auto bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h2 className="text-lg font-semibold">{selected.subscriber}</h2>
                <p className="text-xs text-slate-500">Attempt #{selected.id} · {new Date(selected.created_at).toLocaleString()} · policy v{selected.policy_version}</p>
              </div>
              <button onClick={() => setSelected(null)} className="btn-secondary">Close</button>
            </div>
            <AttemptWork a={selected} />
          </aside>
        </div>
      )}
    </div>
  );
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-slate-400">{hint}</div>}
    </div>
  );
}

function Reasons({ stats }: { stats: Stats }) {
  const max = Math.max(...stats.by_reason.map((r) => r.attempts), 1);
  const top = stats.by_reason[0];
  return (
    <div className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="font-semibold">Why subscribers leave</h2>
        {top && <span className="text-sm text-slate-500">Top reason: <b>{CATEGORY_LABEL[top.category]}</b> ({Math.round(100 * top.attempts / stats.attempts)}% of attempts). Try a policy change in the Simulator.</span>}
      </div>
      <div className="space-y-1.5">
        {stats.by_reason.map((r) => (
          <div key={r.category} className="flex items-center gap-3 text-sm">
            <span className="w-36 shrink-0 text-slate-600">{CATEGORY_LABEL[r.category] ?? r.category}</span>
            <div className="relative h-5 flex-1 rounded bg-slate-100">
              <div className="absolute inset-y-0 left-0 rounded bg-slate-300" style={{ width: `${(100 * r.attempts) / max}%` }} />
              <div className="absolute inset-y-0 left-0 rounded bg-teal-600" style={{ width: `${(100 * r.saved) / max}%` }} />
            </div>
            <span className="w-28 shrink-0 text-right tabular-nums text-slate-600">{r.saved} saved / {r.attempts}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
