"use client";

import { useEffect, useRef } from "react";
import { useChatStream } from "../hooks/useChatStream";
import { ChatMessage } from "../components/ChatMessage";
import { ChatInput } from "../components/ChatInput";

export default function Home() {
  const { messages, status, sendMessage, approveToolCall } = useChatStream();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const isDisabled = status === "streaming" || status === "awaiting_approval";

  return (
    <div className="relative z-10 flex h-screen flex-col" style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      {/* Header */}
      <header
        className="flex items-center gap-4 px-8 py-5"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <div
          className="flex h-9 w-9 items-center justify-center rounded-lg text-sm font-bold"
          style={{ background: 'var(--accent)', color: 'var(--user-text)' }}
        >
          ai
        </div>
        <div>
          <h1
            className="text-xl font-semibold tracking-tight"
            style={{ fontFamily: "'DM Serif Display', Georgia, serif", color: 'var(--text-primary)' }}
          >
            aigent
          </h1>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Product search assistant
          </p>
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl px-6 py-6">
          {messages.length === 0 && (
            <div className="flex h-[60vh] flex-col items-center justify-center text-center">
              <div
                className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl text-2xl font-bold"
                style={{ background: 'var(--accent-soft)', color: 'var(--accent)', fontFamily: "'DM Serif Display', Georgia, serif" }}
              >
                ai
              </div>
              <h2
                className="mb-2 text-2xl tracking-tight"
                style={{ fontFamily: "'DM Serif Display', Georgia, serif", color: 'var(--text-primary)' }}
              >
                What can I find for you?
              </h2>
              <p className="max-w-sm text-sm leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                Search for products, compare prices across retailers, and read reviews — all in one place.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-2">
                {[
                  "Find wireless headphones under $100",
                  "Compare MacBook Air prices",
                  "Best rated mechanical keyboards",
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => sendMessage(suggestion)}
                    className="rounded-full px-4 py-2 text-xs font-medium transition-all duration-200 hover:scale-[1.02]"
                    style={{
                      background: 'var(--bg-secondary)',
                      color: 'var(--text-secondary)',
                      border: '1px solid var(--border-light)',
                    }}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-1">
            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                message={msg}
                onApprove={() => approveToolCall(true)}
                onDeny={() => approveToolCall(false)}
              />
            ))}
          </div>

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="relative" style={{ borderTop: '1px solid var(--border)' }}>
        {status === "streaming" && (
          <div
            className="absolute -top-8 left-1/2 -translate-x-1/2 rounded-full px-4 py-1.5 text-xs font-medium animate-fade-in-up"
            style={{ background: 'var(--accent-soft)', color: 'var(--accent)', boxShadow: 'var(--shadow-sm)' }}
          >
            <span className="animate-shimmer inline-block">Searching...</span>
          </div>
        )}
        {status === "awaiting_approval" && (
          <div
            className="absolute -top-8 left-1/2 -translate-x-1/2 rounded-full px-4 py-1.5 text-xs font-medium animate-fade-in-up"
            style={{ background: '#fef3c7', color: '#92400e', boxShadow: 'var(--shadow-sm)' }}
          >
            Approval needed
          </div>
        )}
        <div className="mx-auto max-w-2xl px-6 py-4">
          <ChatInput onSend={sendMessage} disabled={isDisabled} />
        </div>
      </div>
    </div>
  );
}
