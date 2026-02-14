"use client";

import type { ToolCall } from "../types";

interface Props {
  toolCall: ToolCall;
  showApproval: boolean;
  onApprove?: () => void;
  onDeny?: () => void;
}

const TOOL_LABELS: Record<string, { label: string; icon: string }> = {
  search_product: { label: "Search Products", icon: "search" },
  compare_prices: { label: "Compare Prices", icon: "compare" },
  get_reviews: { label: "Get Reviews", icon: "reviews" },
  calculate_budget: { label: "Calculate Budget", icon: "budget" },
};

function ToolIcon({ type }: { type: string }) {
  const icons: Record<string, string> = {
    search: "M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z",
    compare: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z",
    reviews: "M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z",
    budget: "M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z",
  };
  const d = icons[type] || icons.search;
  return (
    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d={d} />
    </svg>
  );
}

export function ToolCallCard({ toolCall, showApproval, onApprove, onDeny }: Props) {
  const meta = TOOL_LABELS[toolCall.name] || { label: toolCall.name, icon: "search" };

  return (
    <div
      className="overflow-hidden rounded-xl text-sm"
      style={{ border: '1px solid var(--border)', background: 'var(--bg-chat)' }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-3.5 py-2"
        style={{ borderBottom: '1px solid var(--border-light)', background: 'var(--bg-secondary)' }}
      >
        <ToolIcon type={meta.icon} />
        <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
          {meta.label}
        </span>
      </div>

      {/* Args */}
      <div className="px-3.5 py-2.5">
        <pre
          className="text-xs leading-relaxed overflow-x-auto"
          style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)' }}
        >
          {JSON.stringify(toolCall.args, null, 2)}
        </pre>
      </div>

      {/* Approval buttons */}
      {showApproval && (
        <div
          className="flex gap-2 px-3.5 py-2.5"
          style={{ borderTop: '1px solid var(--border-light)', background: 'var(--bg-secondary)' }}
        >
          <button
            onClick={onApprove}
            className="flex-1 rounded-lg px-3 py-2 text-xs font-semibold text-white transition-all duration-150 hover:scale-[1.01] active:scale-[0.99]"
            style={{ background: '#16a34a' }}
          >
            Approve
          </button>
          <button
            onClick={onDeny}
            className="flex-1 rounded-lg px-3 py-2 text-xs font-semibold transition-all duration-150 hover:scale-[1.01] active:scale-[0.99]"
            style={{ background: 'var(--bg-primary)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
          >
            Deny
          </button>
        </div>
      )}
    </div>
  );
}
