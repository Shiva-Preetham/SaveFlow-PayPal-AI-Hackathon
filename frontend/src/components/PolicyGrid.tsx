import type { ColDef, ICellRendererParams } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { useMemo } from "react";
import type { Rules } from "../lib/api";
import { gridTheme } from "./grid";

type Kind = "bool" | "int" | "list" | "map";
type Row = { field: keyof Rules; label: string; kind: Kind; help: string; value: unknown };

const FIELDS: Omit<Row, "value">[] = [
  { field: "pause_enabled", label: "Offer pauses", kind: "bool", help: "Suspend in PayPal, resume automatically" },
  { field: "max_pause_months", label: "Longest pause (months)", kind: "int", help: "1–6" },
  { field: "min_paid_months_for_pause", label: "Pause only after N paid months", kind: "int", help: "0 = anyone" },
  { field: "discount_enabled", label: "Offer discounts", kind: "bool", help: "Switches to a discount plan (buyer approves in PayPal)" },
  { field: "max_discount_pct", label: "Largest discount (%)", kind: "int", help: "Only discount plans at or below this are offered" },
  { field: "min_paid_months_for_discount", label: "Discount only after N paid months", kind: "int", help: "Protects against discount hunters" },
  { field: "discount_only_for", label: "Discount only for reasons", kind: "list", help: "Comma-separated: price, competitor… (empty = all)" },
  { field: "downgrade_enabled", label: "Offer cheaper plan", kind: "bool", help: "Switch to Lite" },
  { field: "max_offers_per_subscriber", label: "Offers per subscriber, ever", kind: "int", help: "0 = never make offers" },
  { field: "no_offer_for", label: "No offer for reasons", kind: "list", help: "e.g. product_problem: just let them go" },
  { field: "prefer", label: "Preferred offer per reason", kind: "map", help: "e.g. price:discount, temporary:pause" },
];

function show(kind: Kind, v: unknown): string {
  if (kind === "list") return (v as string[]).join(", ");
  if (kind === "map") return Object.entries(v as Record<string, string>).map(([k, x]) => `${k}:${x}`).join(", ");
  return String(v);
}

function parse(kind: Kind, raw: unknown): unknown {
  if (kind === "bool") return Boolean(raw);
  if (kind === "int") return Number(raw);
  const parts = String(raw ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  if (kind === "list") return parts;
  return Object.fromEntries(parts.map((p) => p.split(":").map((s) => s.trim())).filter((p) => p.length === 2));
}

/** The merchant's policy as an editable grid: the non-AI way to change rules. The server validates every edit. */
export default function PolicyGrid({ rules, onChange, changed = [] }: { rules: Rules; onChange: (r: Rules) => void; changed?: string[] }) {
  const rows = useMemo<Row[]>(() => FIELDS.map((f) => ({ ...f, value: rules[f.field] })), [rules]);
  const cols = useMemo<ColDef<Row>[]>(() => [
    { field: "label", headerName: "Rule", flex: 1.3 },
    {
      field: "value", headerName: "Value", flex: 1, editable: true, singleClickEdit: true,
      cellEditorSelector: (p) => p.data?.kind === "bool" ? { component: "agCheckboxCellEditor" }
        : p.data?.kind === "int" ? { component: "agNumberCellEditor", params: { min: 0, max: 100, precision: 0 } }
        : { component: "agTextCellEditor" },
      cellRenderer: (p: ICellRendererParams<Row>) => p.data?.kind === "bool"
        ? <span className={p.value ? "text-emerald-700" : "text-slate-400"}>{p.value ? "✓ Yes" : "✗ No"}</span>
        : <span className="font-medium">{String(p.value ?? "") || <span className="text-slate-400">(none)</span>}</span>,
      valueGetter: (p) => (p.data?.kind === "list" || p.data?.kind === "map") ? show(p.data.kind, p.data.value) : p.data?.value,
      valueSetter: (p) => {
        if (!p.data) return false;
        onChange({ ...rules, [p.data.field]: parse(p.data.kind, p.newValue) });
        return true;
      },
    },
    { field: "help", headerName: "Notes", flex: 1.4, cellClass: "text-slate-500" },
  ], [rules, onChange]);

  return (
    <div style={{ height: 470 }}>
      <AgGridReact<Row> theme={gridTheme} rowData={rows} columnDefs={cols} getRowId={(p) => p.data.field}
        rowClassRules={{ "!bg-amber-50": (p) => !!p.data && changed.includes(p.data.field) }} stopEditingWhenCellsLoseFocus />
    </div>
  );
}
