"use client";

import type { ChatMessage as ChatMessageType } from "../types";
import { ToolCallCard } from "./ToolCallCard";
import { ReceiptCard } from "./ReceiptCard";

interface Props {
  message: ChatMessageType;
  onApprove?: () => void;
  onDeny?: () => void;
}

export function ChatMessage({ message, onApprove, onDeny }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-gray-100 text-gray-900"
        }`}
      >
        {message.content && (
          <p className="whitespace-pre-wrap">{message.content}</p>
        )}

        {message.isStreaming && !message.content && (
          <span className="animate-pulse text-gray-400">Thinking...</span>
        )}

        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 space-y-2">
            {message.toolCalls.map((tc, i) => (
              <ToolCallCard
                key={`${tc.name}-${i}`}
                toolCall={tc}
                showApproval={!!message.isApprovalRequired}
                onApprove={onApprove}
                onDeny={onDeny}
              />
            ))}
          </div>
        )}

        {message.receipt && (
          <div className="mt-2">
            <ReceiptCard receipt={message.receipt} />
          </div>
        )}
      </div>
    </div>
  );
}
