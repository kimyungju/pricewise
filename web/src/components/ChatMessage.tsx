"use client";

import type { ChatMessage as ChatMessageType } from "../types";
import { ToolCallCard } from "./ToolCallCard";
import { ReceiptCard } from "./ReceiptCard";

interface Props {
  message: ChatMessageType;
  onApprove?: () => void;
  onDeny?: () => void;
}

function cleanContent(content: string, hasReceipt: boolean): string {
  if (!content) return "";
  if (!hasReceipt) return content;
  // When a receipt exists, the content often contains raw JSON from the
  // structured response. Strip it: find the first '{' that looks like
  // the start of a JSON object and truncate there.
  const jsonStart = content.indexOf('{"');
  if (jsonStart === -1) return content;
  const cleaned = content.substring(0, jsonStart).trim();
  return cleaned;
}

export function ChatMessage({ message, onApprove, onDeny }: Props) {
  const isUser = message.role === "user";
  const displayContent = cleanContent(message.content, !!message.receipt);

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3 animate-fade-in-up`}
    >
      {!isUser && (
        <div
          className="mr-3 mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-[10px] font-bold"
          style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}
        >
          ai
        </div>
      )}

      <div className={`max-w-[75%] ${isUser ? "" : ""}`}>
        {/* Text bubble */}
        {(displayContent || (message.isStreaming && !displayContent && !message.toolCalls?.length)) && (
          <div
            className={`rounded-2xl px-4 py-2.5 text-[14px] leading-relaxed ${
              isUser ? "rounded-br-md" : "rounded-bl-md"
            }`}
            style={
              isUser
                ? { background: 'var(--user-bg)', color: 'var(--user-text)' }
                : { background: 'var(--bg-chat)', color: 'var(--text-primary)', boxShadow: 'var(--shadow-sm)', border: '1px solid var(--border-light)' }
            }
          >
            {displayContent ? (
              <p className="whitespace-pre-wrap">{displayContent}</p>
            ) : (
              <span className="animate-shimmer inline-block text-sm" style={{ color: 'var(--text-muted)' }}>
                Thinking...
              </span>
            )}
          </div>
        )}

        {/* Tool calls */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 space-y-2 animate-slide-in">
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

        {/* Receipt */}
        {message.receipt && (
          <div className="mt-2 animate-fade-in-up">
            <ReceiptCard receipt={message.receipt} />
          </div>
        )}
      </div>
    </div>
  );
}
