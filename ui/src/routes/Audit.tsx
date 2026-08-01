import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Confidence } from "../components/Badges";
import { listAudit } from "../lib/api";
import { timestamp } from "../lib/format";

// Deliberately a ledger. Auditability is a feature whose UI should look boring.
export default function Audit() {
  const { data, isPending, error } = useQuery({ queryKey: ["audit"], queryFn: listAudit });

  if (isPending) return <p className="text-sm text-neutral-500">Loading…</p>;
  if (error) return <p className="text-sm text-red-600">{String(error)}</p>;

  if (!data || data.actions.length === 0) {
    return (
      <div className="rounded border border-dashed border-neutral-300 p-10 text-center text-sm text-neutral-500 dark:border-neutral-700">
        No reviews recorded yet. Approve, edit, or reject a ticket and it will appear here.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-neutral-500">
          <tr className="border-b border-neutral-200 dark:border-neutral-800">
            <th className="py-2 pr-4 font-medium">When</th>
            <th className="py-2 pr-4 font-medium">Who</th>
            <th className="py-2 pr-4 font-medium">Action</th>
            <th className="py-2 pr-4 font-medium">Ticket</th>
            <th className="py-2 pr-4 font-medium">Route at decision</th>
            <th className="py-2 pr-4 font-medium">Confidence</th>
            <th className="py-2 font-medium">Note</th>
          </tr>
        </thead>
        <tbody>
          {data.actions.map((a) => (
            <tr key={a.id} className="border-b border-neutral-100 dark:border-neutral-900">
              <td className="py-2 pr-4 whitespace-nowrap text-neutral-500">{timestamp(a.created_at)}</td>
              <td className="py-2 pr-4">{a.reviewer}</td>
              <td className="py-2 pr-4 font-medium">{a.action}</td>
              <td className="py-2 pr-4">
                <Link to={`/tickets/${a.ticket_id}`} className="underline-offset-2 hover:underline">
                  {a.subject}
                </Link>
              </td>
              <td className="py-2 pr-4 text-neutral-500">{a.route?.replace(/_/g, " ") ?? "—"}</td>
              <td className="py-2 pr-4"><Confidence value={a.composite_confidence} /></td>
              <td className="py-2 text-neutral-500">{a.note ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
