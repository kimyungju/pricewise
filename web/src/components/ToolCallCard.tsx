"use client";

import type { ToolCall } from "../types";

interface Props {
  toolCall: ToolCall;
  showApproval: boolean;
  onApprove?: () => void;
  onDeny?: () => void;
}

export function ToolCallCard({ toolCall, showApproval, onApprove, onDeny }: Props) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
      <div className="font-medium text-amber-800">
        Tool: {toolCall.name}
      </div>
      <pre className="mt-1 text-xs text-amber-700 overflow-x-auto">
        {JSON.stringify(toolCall.args, null, 2)}
      </pre>

      {showApproval && (
        <div className="mt-2 flex gap-2">
          <button
            onClick={onApprove}
            className="rounded-md bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700"
          >
            Approve
          </button>
          <button
            onClick={onDeny}
            className="rounded-md bg-red-600 px-3 py-1 text-xs font-medium text-white hover:bg-red-700"
          >
            Deny
          </button>
        </div>
      )}
    </div>
  );
}
