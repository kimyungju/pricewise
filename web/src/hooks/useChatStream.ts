"use client";

import { useState, useCallback, useRef } from "react";
import type { ChatMessage, ChatStatus, ToolCall, Receipt } from "../types";

const API_BASE = "/api/chat";

function generateId(): string {
  return Math.random().toString(36).substring(2, 10);
}

async function readSSEStream(
  response: Response,
  handlers: {
    onToken: (content: string) => void;
    onApprovalRequired: (toolCalls: ToolCall[]) => void;
    onReceipt: (receipt: Receipt) => void;
    onToolCall: (toolCall: ToolCall) => void;
    onDone: () => void;
    onError: (message: string) => void;
  }
) {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    let currentEvent = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith("data: ") && currentEvent) {
        const data = JSON.parse(line.slice(6));
        switch (currentEvent) {
          case "token":
            handlers.onToken(data.content);
            break;
          case "tool_call":
            handlers.onToolCall(data);
            break;
          case "approval_required":
            handlers.onApprovalRequired(data.tool_calls);
            break;
          case "receipt":
            handlers.onReceipt(data);
            break;
          case "done":
            handlers.onDone();
            break;
          case "error":
            handlers.onError(data.message);
            break;
        }
        currentEvent = "";
      }
    }
  }
}

export function useChatStream() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const pendingToolCallsRef = useRef<ToolCall[]>([]);

  const createSession = useCallback(async () => {
    const resp = await fetch(`${API_BASE}/sessions`, { method: "POST" });
    const data = await resp.json();
    setSessionId(data.session_id);
    return data.session_id;
  }, []);

  const sendMessage = useCallback(
    async (content: string) => {
      let sid = sessionId;
      if (!sid) {
        sid = await createSession();
      }

      const userMsg: ChatMessage = {
        id: generateId(),
        role: "user",
        content,
      };
      const assistantId = generateId();
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setStatus("streaming");

      const response = await fetch(`${API_BASE}/sessions/${sid}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });

      await readSSEStream(response, {
        onToken: (token) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content + token }
                : m
            )
          );
        },
        onToolCall: (toolCall) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, toolCalls: [...(m.toolCalls || []), toolCall] }
                : m
            )
          );
        },
        onApprovalRequired: (toolCalls) => {
          pendingToolCallsRef.current = toolCalls;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    isStreaming: false,
                    isApprovalRequired: true,
                    toolCalls: toolCalls,
                  }
                : m
            )
          );
          setStatus("awaiting_approval");
        },
        onReceipt: (receipt) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, receipt } : m
            )
          );
        },
        onDone: () => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, isStreaming: false } : m
            )
          );
          setStatus("idle");
        },
        onError: (message) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content || `Error: ${message}`, isStreaming: false }
                : m
            )
          );
          setStatus("error");
        },
      });
    },
    [sessionId, createSession]
  );

  const approveToolCall = useCallback(
    async (approved: boolean) => {
      if (!sessionId) return;

      setStatus("streaming");

      const assistantId = generateId();
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        isStreaming: true,
      };

      setMessages((prev) => [
        ...prev.map((m) =>
          m.isApprovalRequired ? { ...m, isApprovalRequired: false } : m
        ),
        assistantMsg,
      ]);

      const response = await fetch(
        `${API_BASE}/sessions/${sessionId}/approve`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ approved }),
        }
      );

      await readSSEStream(response, {
        onToken: (token) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content + token }
                : m
            )
          );
        },
        onToolCall: (toolCall) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, toolCalls: [...(m.toolCalls || []), toolCall] }
                : m
            )
          );
        },
        onApprovalRequired: (toolCalls) => {
          pendingToolCallsRef.current = toolCalls;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, isStreaming: false, isApprovalRequired: true, toolCalls: toolCalls }
                : m
            )
          );
          setStatus("awaiting_approval");
        },
        onReceipt: (receipt) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, receipt } : m
            )
          );
        },
        onDone: () => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, isStreaming: false } : m
            )
          );
          setStatus("idle");
        },
        onError: (message) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content || `Error: ${message}`, isStreaming: false }
                : m
            )
          );
          setStatus("error");
        },
      });
    },
    [sessionId]
  );

  return { messages, status, sendMessage, approveToolCall };
}
