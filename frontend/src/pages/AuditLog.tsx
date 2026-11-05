import type { ColDef } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { useEffect, useMemo, useState } from "react";
import { gridTheme } from "../components/grid";
import type { AuditEntry } from "../lib/api";
import { api } from "../lib/api";

export default function AuditLog() {
  const [rows, setRows] = useState<AuditEntry[]>([]);
  const [selected, setSelected] = useState<AuditEntry | null>(null);
  const [quick, setQuick] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.audit().then(setRows).catch((e) => setError(e.message)); }, []);

  const cols = useMemo<ColDef<AuditEntry>[]>(() => [
    { field: "id", width: 80 },
    { field: "created_at", headerName: "When", width: 190, valueFormatter: (p) => new Date(p.value).toLocaleString() },
    { field: "action", width: 200 },
    { field: "attempt_id", headerName: "Attempt", width: 100 },
    { field: "subscriber_id", headerName: "Subscriber", width: 110 },
    { headerName: "Detail", flex: 1, valueGetter: (p) => JSON.stringify(p.data?.detail), tooltipValueGetter: (p) => p.value },
  ], []);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Audit log</h1>
          <p className="text-sm text-slate-500">Every agent decision, guardrail result, policy change, webhook and PayPal call. Click a row for the full record.</p>
        </div>
        <input value={quick} onChange={(e) => setQuick(e.target.value)} placeholder="Filter…" className="w-64 rounded-md border border-slate-300 px-3 py-1.5 text-sm" />
      </div>
      {error && <p className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      <div style={{ height: 480 }}>
        <AgGridReact<AuditEntry> theme={gridTheme} rowData={rows} columnDefs={cols} quickFilterText={quick}
          defaultColDef={{ sortable: true, filter: true, resizable: true }} pagination paginationPageSize={50}
          onRowClicked={(e) => setSelected(e.data ?? null)} />
      </div>
      {selected && (
        <pre className="max-h-96 overflow-auto rounded-xl bg-slate-900 p-4 text-xs text-slate-100">{JSON.stringify(selected, null, 2)}</pre>
      )}
    </div>
  );
}
