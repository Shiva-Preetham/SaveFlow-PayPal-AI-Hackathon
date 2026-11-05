import type { ICellRendererParams } from "ag-grid-community";
import { themeQuartz } from "ag-grid-community";
import { CATEGORY_LABEL, money } from "../lib/api";

// One theme for every grid in the merchant workspace.
export const gridTheme = themeQuartz.withParams({
  accentColor: "#0d9488",
  fontFamily: "inherit",
  fontSize: 13,
  headerBackgroundColor: "#f8fafc",
  headerFontWeight: 600,
  rowHoverColor: "#f0fdfa",
  selectedRowBackgroundColor: "#ccfbf1",
  borderColor: "#e2e8f0",
  wrapperBorderRadius: 10,
  spacing: 6,
});

const OUTCOME_STYLE: Record<string, string> = {
  saved: "bg-emerald-100 text-emerald-800",
  awaiting_approval: "bg-amber-100 text-amber-800",
  offered: "bg-sky-100 text-sky-800",
  no_offer: "bg-slate-100 text-slate-700",
  cancelled: "bg-rose-100 text-rose-800",
  declined: "bg-rose-100 text-rose-800",
};
const OUTCOME_LABEL: Record<string, string> = {
  saved: "Saved", awaiting_approval: "Awaiting PayPal approval", offered: "Offer open",
  no_offer: "No offer", cancelled: "Cancelled", declined: "Declined",
};

export function Pill({ className, children, title }: { className: string; children: React.ReactNode; title?: string }) {
  return <span title={title} className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>{children}</span>;
}

export function OutcomeCell(p: ICellRendererParams) {
  if (!p.value) return null;
  return <Pill className={OUTCOME_STYLE[p.value] ?? "bg-slate-100"}>{OUTCOME_LABEL[p.value] ?? p.value}</Pill>;
}

const CATEGORY_STYLE: Record<string, string> = {
  temporary: "bg-violet-100 text-violet-800", price: "bg-orange-100 text-orange-800",
  low_usage: "bg-slate-200 text-slate-700", product_problem: "bg-rose-100 text-rose-800",
  competitor: "bg-blue-100 text-blue-800", other: "bg-zinc-100 text-zinc-700",
};

export function CategoryCell(p: ICellRendererParams) {
  if (!p.value) return null;
  return <Pill className={CATEGORY_STYLE[p.value] ?? "bg-slate-100"}>{CATEGORY_LABEL[p.value] ?? p.value}</Pill>;
}

export function GuardrailCell(p: ICellRendererParams) {
  const injection = p.data?.injection_suspected;
  const v = p.value as string;
  return (
    <span className="flex items-center gap-1">
      {v === "blocked" && <Pill className="bg-rose-600 text-white" title="AI proposed an out-of-policy offer; code replaced it">Blocked</Pill>}
      {v === "passed" && <Pill className="bg-emerald-50 text-emerald-700">Passed</Pill>}
      {v === "fallback" && <Pill className="bg-slate-200 text-slate-700" title="AI unavailable: rule-based default">Fallback</Pill>}
      {injection && <Pill className="bg-amber-500 text-white" title="Prompt injection suspected">Injection</Pill>}
    </span>
  );
}

export function MoneyCell(p: ICellRendererParams) {
  if (p.value == null || p.value === 0) return <span className="text-slate-400">—</span>;
  return <span className="font-medium tabular-nums">{money(p.value)}</span>;
}

export function SourceCell(p: ICellRendererParams) {
  const map: Record<string, string> = { gemini: "Gemini", cache: "Gemini (cached)", fallback: "Fallback", seed: "Demo data" };
  return <span className="text-slate-500">{map[p.value] ?? p.value}</span>;
}

export function SubscriberCell(p: ICellRendererParams) {
  return (
    <span className="flex items-center gap-1.5">
      {p.value}
      {p.data?.is_live && <Pill className="bg-[#003087] text-white" title="Backed by a real PayPal sandbox subscription">PayPal live</Pill>}
    </span>
  );
}
