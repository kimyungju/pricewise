"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage as ChatMessageType } from "../types";
import { ToolCallCard } from "./ToolCallCard";
import { ReceiptCard } from "./ReceiptCard";

interface Props {
  message: ChatMessageType;
  staggerIndex?: number;
  onApprove?: () => void;
  onDeny?: () => void;
}

export function ChatMessage({
  message,
  staggerIndex = 0,
  onApprove,
  onDeny,
}: Props) {
  const isUser = message.role === "user";
  const displayContent = message.content;

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3 ${
        isUser ? "animate-slide-in-right" : "animate-slide-in-left"
      }`}
      style={{ "--stagger": staggerIndex } as React.CSSProperties}
    >
      {!isUser && (
        <div
          className="mr-3 mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[10px] font-bold"
          style={{
            background: "var(--bg-sidebar)",
            color: "var(--accent)",
            fontFamily: "'Playfair Display', Georgia, serif",
          }}
        >
          a.
        </div>
      )}

      <div className={`max-w-[75%]`}>
        {/* Text bubble */}
        {(displayContent ||
          (message.isStreaming &&
            !displayContent &&
            !message.toolCalls?.length)) && (
          <div
            className={`rounded-2xl px-4 py-2.5 text-[14px] leading-relaxed ${
              isUser ? "rounded-br-md" : "rounded-bl-md"
            }`}
            style={
              isUser
                ? {
                    background: "var(--user-bg)",
                    color: "var(--user-text)",
                  }
                : {
                    background: "var(--bg-chat)",
                    color: "var(--text-primary)",
                    boxShadow: "var(--shadow-sm)",
                    border: "1px solid var(--border-light)",
                  }
            }
          >
            {displayContent ? (
              isUser ? (
                <p className="whitespace-pre-wrap">{displayContent}</p>
              ) : (
                <div className="prose-editorial">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {displayContent}
                  </ReactMarkdown>
                </div>
              )
            ) : (
              <span className="flex items-center gap-2 text-sm">
                <span className="flex items-center gap-1">
                  <span
                    className="typing-dot inline-block h-1.5 w-1.5 rounded-full"
                    style={{ background: "var(--accent)" }}
                  />
                  <span
                    className="typing-dot inline-block h-1.5 w-1.5 rounded-full"
                    style={{ background: "var(--accent)" }}
                  />
                  <span
                    className="typing-dot inline-block h-1.5 w-1.5 rounded-full"
                    style={{ background: "var(--accent)" }}
                  />
                </span>
                <span style={{ color: "var(--text-muted)" }}>
                  Composing...
                </span>
              </span>
            )}
          </div>
        )}

        {/* Tool calls */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 space-y-2 animate-scale-in">
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
