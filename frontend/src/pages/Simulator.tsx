import type { ColDef } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import PolicyGrid from "../components/PolicyGrid";
import { CategoryCell, MoneyCell, OutcomeCell, gridTheme } from "../components/grid";
import type { Rules, SimResult, SimRow } from "../lib/api";
import { api, money } from "../lib/api";

export default function Simulator() {
  const [rules, setRules] = useState<Rules | null>(null);
  const [result, setResult] = useState<SimResult | null>(null);
  const [onlyChanged, setOnlyChanged] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback((r: Rules) => {
    setRules(r);
    api.simulate(r).then((res) => { setResult(res); setError(null); }).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    let fromPolicy: Rules | null = null;
    try {
      fromPolicy = JSON.parse(sessionStorage.getItem("saveflow.simulate") ?? "null");
      sessionStorage.removeItem("saveflow.simulate");
    } catch { /* storage blocked */ }
    if (fromPolicy) run(fromPolicy);
    else api.policy().then((p) => run({ ...p.rules, max_discount_pct: 20, no_offer_for: ["product_problem"] })).catch((e) => setError(e.message));
  }, [run]);

  const cols = useMemo<ColDef<SimRow>[]>(() => [
    { field: "subscriber", width: 150 },
    { field: "category", headerName: "Reason type", width: 150, cellRenderer: CategoryCell },
    { field: "reason", flex: 1.5, minWidth: 200, tooltipField: "reason" },
    { field: "months_paid", headerName: "Months", width: 95, type: "rightAligned" },
    { field: "original_offer", headerName: "Offer made", flex: 1, minWidth: 160 },
    { field: "original_outcome", headerName: "What happened", width: 150, cellRenderer: OutcomeCell },
    { field: "simulated_offer", headerName: "Offer under new policy", flex: 1, minWidth: 180, cellClass: (p) => (p.data?.changed ? "font-semibold text-teal-800" : "") },
    { field: "revenue_before", headerName: "Value offered (before)", width: 150, cellRenderer: MoneyCell, type: "rightAligned" },
    { field: "revenue_after", headerName: "Value offered (after)", width: 150, cellRenderer: MoneyCell, type: "rightAligned" },
  ], []);

  const rows = useMemo(() => (result?.rows ?? []).filter((r) => !onlyChanged || r.changed), [result, onlyChanged]);
  const t = result?.totals;
  const pinned = useMemo(() => t ? [{
    subscriber: "Total", reason: `${t.changed} of ${t.attempts} offers would change`, original_offer: "", simulated_offer: "",
    revenue_before: t.revenue_offered_before, revenue_after: t.revenue_offered_after,
  } as unknown as SimRow] : [], [t]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">What-if simulator</h1>
        <p className="text-sm text-slate-500">
          Replay past cancel attempts against a proposed policy before turning it on. Deterministic and LLM-free: it keeps the
          AI's original pick when the new policy still allows it, otherwise uses the safe default.
          It shows <b>offers that would have been made</b>, not whether subscribers would accept them.
        </p>
      </div>
      {error && <p className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
        <section className="space-y-2">
          <h2 className="font-semibold">Proposed policy</h2>
          {rules && <PolicyGrid rules={rules} onChange={run} />}
        </section>
        <section className="space-y-3">
          {t && (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Stat label="Offers that change" value={`${t.changed} / ${t.attempts}`} />
              <Stat label="No-offer cancels" value={`${t.no_offer_before} → ${t.no_offer_after}`} />
              <Stat label="Value offered before" value={money(t.revenue_offered_before)} />
              <Stat label="Value offered after" value={money(t.revenue_offered_after)}
                delta={t.revenue_offered_after - t.revenue_offered_before} />
            </div>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={onlyChanged} onChange={(e) => setOnlyChanged(e.target.checked)} /> Show only attempts whose offer changes
          </label>
          <div style={{ height: 470 }}>
            <AgGridReact<SimRow> theme={gridTheme} rowData={rows} columnDefs={cols} pinnedBottomRowData={pinned}
              defaultColDef={{ sortable: true, filter: true, resizable: true }} tooltipShowDelay={300}
              rowClassRules={{ "!bg-teal-50": (p) => !!p.data?.changed && p.node.rowPinned == null }} />
          </div>
          <p className="text-xs text-slate-500">“Value offered” = 12-month revenue if the subscriber accepted and stayed. Use it to compare policies, not as a forecast.</p>
        </section>
      </div>
    </div>
  );
}

function Stat({ label, value, delta }: { label: string; value: string; delta?: number }) {
  return (
    <div className="rounded-xl bg-white p-3 ring-1 ring-slate-200">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
      {delta != null && delta !== 0 && <div className={`text-xs ${delta > 0 ? "text-emerald-700" : "text-rose-700"}`}>{delta > 0 ? "+" : ""}{money(delta)}</div>}
    </div>
  );
}
