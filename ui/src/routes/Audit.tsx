import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ErrorNote, Skeleton } from "../components/Async";
import { RouteBadge } from "../components/Badges";
import { ConfidenceMeter } from "../components/Meter";
import { getStatus, listAudit } from "../lib/api";
import { timestamp } from "../lib/format";
import { usePolicy } from "../lib/usePolicy";

const ACTION_TONE: Record<string, string> = {
  approve: "text-teal",
  edit: "text-mustard",
  reject: "text-rust",
};

// Deliberately a ledger: one row per decision, unaggregated, in the order they happened.
export default function Audit() {
  const { data, isPending, error } = useQuery({ queryKey: ["audit"], queryFn: listAudit });
  const status = useQuery({ queryKey: ["status"], queryFn: getStatus });
  const policy = usePolicy();

  if (isPending) return <Skeleton />;
  if (error) return <ErrorNote error={error} what="the audit trail" />;

  if (!data || data.actions.length === 0) {
    return (
      <div className="rounded-[2px] border border-dashed border-rule-2 p-10 text-center">
        <p className="text-sm text-ink-2">No reviews recorded yet.</p>
        <p className="prose-human mt-1 text-xs text-ink-3">
          Approve, edit, or reject a ticket and it will appear here.
        </p>
      </div>
    );
  }

  const reasons = Object.entries(status.data?.reject_reasons ?? {});

  return (
    <div className="space-y-4">
      <header className="space-y-1">
        <h1 className="text-lg font-semibold tracking-tight">Audit trail</h1>
        <p className="prose-human max-w-2xl text-sm text-ink-2">
          Every human decision, with the confidence the agent reported at the moment it was
          made. Append-only.
        </p>
      </header>

      {reasons.length > 0 && (
        <div className="card p-3">
          <p className="eyebrow">why drafts were rejected</p>
          <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs">
            {reasons.map(([reason, n]) => (
              <li key={reason} className="text-ink-2">
                {reason.replace(/_/g, " ")} <span className="tabular-nums text-ink-3">{n}</span>
              </li>
            ))}
          </ul>
          <p className="prose-human mt-2 max-w-2xl text-[11px] leading-relaxed text-ink-3">
            These are the cheapest labelled examples this project gets. The golden set is 60
            tickets and every headline metric is limited by that, so a reviewer picking a reason
            is doing eval work, not filing a complaint.
          </p>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <caption className="sr-only">Review actions, newest first</caption>
          <thead>
            <tr className="rule-row text-left">
              <th className="eyebrow py-2 pr-4 font-medium">when</th>
              <th className="eyebrow py-2 pr-4 font-medium">who</th>
              <th className="eyebrow py-2 pr-4 font-medium">action</th>
              <th className="eyebrow py-2 pr-4 font-medium">ticket</th>
              <th className="eyebrow py-2 pr-4 font-medium">route at decision</th>
              <th className="eyebrow py-2 pr-4 font-medium">confidence</th>
              <th className="eyebrow py-2 font-medium">note</th>
            </tr>
          </thead>
          <tbody>
            {data.actions.map((a) => (
              <tr key={a.id} className="rule-row transition-colors hover:bg-paper-2">
                <td className="whitespace-nowrap py-2 pr-4 tabular-nums text-ink-3">
                  {timestamp(a.created_at)}
                </td>
                <td className="py-2 pr-4 text-ink-2">{a.reviewer}</td>
                <td className={`whitespace-nowrap py-2 pr-4 font-medium ${ACTION_TONE[a.action] ?? ""}`}>
                  {a.action}
                  {a.reason && (
                    <span className="ml-1.5 font-normal text-ink-3">
                      {a.reason.replace(/_/g, " ")}
                    </span>
                  )}
                </td>
                <td className="max-w-[18rem] py-2 pr-4">
                  <Link
                    to={`/tickets/${a.ticket_id}`}
                    className="prose-human block truncate underline-offset-2 hover:underline"
                  >
                    {a.subject}
                  </Link>
                </td>
                <td className="py-2 pr-4">
                  <RouteBadge route={a.route} />
                </td>
                <td className="py-2 pr-4">
                  <ConfidenceMeter value={a.composite_confidence} policy={policy} width="w-16" />
                </td>
                <td className="prose-human py-2 text-ink-3">{a.note ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
