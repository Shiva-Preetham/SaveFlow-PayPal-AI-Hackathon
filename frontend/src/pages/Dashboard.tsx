import type { ColDef } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";

type Attempt = { subscriber: string; reason: string; offer: string; outcome: string; revenueSaved: number };

// Placeholder rows until the backend serves real cancel attempts.
const rows: Attempt[] = [
  { subscriber: "Demo subscriber A", reason: "Travelling for 3 months", offer: "Pause 3 months", outcome: "Saved", revenueSaved: 30 },
  { subscriber: "Demo subscriber B", reason: "Too expensive as a student", offer: "Switch to Lite", outcome: "Pending approval", revenueSaved: 0 },
];

const columns: ColDef<Attempt>[] = [
  { field: "subscriber" },
  { field: "reason", flex: 2 },
  { field: "offer" },
  { field: "outcome" },
  { field: "revenueSaved", headerName: "Revenue saved", valueFormatter: (p) => `$${p.value}` },
];

export default function Dashboard() {
  return (
    <section>
      <h1 className="mb-1 text-xl font-semibold">Cancel attempts</h1>
      <p className="mb-4 text-sm text-slate-500">Demo data</p>
      <div style={{ height: 400 }}>
        <AgGridReact rowData={rows} columnDefs={columns} defaultColDef={{ flex: 1, filter: true, sortable: true }} />
      </div>
    </section>
  );
}
