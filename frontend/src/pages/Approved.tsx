import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";

/** PayPal sends the buyer here after approving a plan change. We confirm with PayPal, tell the opener, and close. */
export default function Approved() {
  const [params] = useSearchParams();
  const [text, setText] = useState("Checking with PayPal…");
  const attempt = Number(params.get("attempt"));
  const cancelled = params.get("cancelled") === "1";

  useEffect(() => {
    if (!attempt) { setText("Missing attempt id."); return; }
    if (cancelled) { setText("You didn't approve the change in PayPal. You can close this window."); return; }
    api.confirm(attempt).then((a) => {
      setText(a.outcome === "saved" ? "Confirmed in PayPal. You can close this window." : "PayPal is still processing; the main window will update shortly.");
      window.opener?.postMessage({ type: "saveflow-approved", attempt }, window.location.origin);
      if (a.outcome === "saved") window.setTimeout(() => window.close(), 1500);
    }).catch((e) => setText(e.message));
  }, [attempt, cancelled]);

  return <div className="mx-auto mt-24 max-w-sm rounded-xl bg-white p-6 text-center ring-1 ring-slate-200">{text}</div>;
}
