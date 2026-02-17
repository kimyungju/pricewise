"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import type { ChatMessage, ChatStatus, ToolCall, Receipt } from "../types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL.replace(/\/+$/, "")}/chat`
  : "/api/chat";
const STORAGE_KEY = "pricewise_session_id";

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
    onToolResult: (name: string, result: string) => void;
    onDone: () => void;
    onError: (message: string) => void;
  },
  signal?: AbortSignal
) {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  if (signal) {
    signal.addEventListener("abort", () => reader.cancel(), { once: true });
  }

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
          case "tool_result":
            handlers.onToolResult(data.name, data.result);
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

function createSSEHandlers(
  assistantId: string,
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>,
  setStatus: React.Dispatch<React.SetStateAction<ChatStatus>>
) {
  return {
    onToken: (token: string) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, content: m.content + token } : m
        )
      );
    },
    onToolCall: (toolCall: ToolCall) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, toolCalls: [...(m.toolCalls || []), toolCall] }
            : m
        )
      );
    },
    onToolResult: (name: string, result: string) => {
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== assistantId || !m.toolCalls) return m;
          const updatedCalls = [...m.toolCalls];
          for (let i = updatedCalls.length - 1; i >= 0; i--) {
            if (updatedCalls[i].name === name && !updatedCalls[i].result) {
              updatedCalls[i] = { ...updatedCalls[i], result };
              break;
            }
          }
          return { ...m, toolCalls: updatedCalls };
        })
      );
    },
    onApprovalRequired: (toolCalls: ToolCall[]) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, isStreaming: false, isApprovalRequired: true, toolCalls }
            : m
        )
      );
      setStatus("awaiting_approval");
    },
    onReceipt: (receipt: Receipt) => {
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, receipt } : m))
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
    onError: (message: string) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: m.content || `Error: ${message}`, isStreaming: false }
            : m
        )
      );
      setStatus("error");
    },
  };
}

export function useChatStream() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const initializedRef = useRef(false);
  const abortRef = useRef<AbortController | null>(null);

  // Rehydrate session from localStorage on mount
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return;

    setSessionId(stored);
    fetch(`${API_BASE}/sessions/${stored}/messages`)
      .then((res) => {
        if (res.ok) return res.json();
        localStorage.removeItem(STORAGE_KEY);
        setSessionId(null);
        return null;
      })
      .then((data) => {
        if (data?.messages?.length) {
          const hydrated: ChatMessage[] = data.messages.map(
            (m: { id: string; role: string; content: string; toolCalls?: ToolCall[] }) => ({
              id: m.id || generateId(),
              role: m.role as "user" | "assistant",
              content: m.content,
              toolCalls: m.toolCalls,
            })
          );
          if (data.receipt) {
            for (let i = hydrated.length - 1; i >= 0; i--) {
              if (hydrated[i].role === "assistant") {
                hydrated[i] = { ...hydrated[i], receipt: data.receipt };
                break;
              }
            }
          }
          setMessages(hydrated);
        }
      })
      .catch(() => {
        localStorage.removeItem(STORAGE_KEY);
        setSessionId(null);
      });
  }, []);

  const createSession = useCallback(async (signal?: AbortSignal) => {
    const resp = await fetch(`${API_BASE}/sessions`, { method: "POST", signal });
    if (!resp.ok) throw new Error("Failed to create session");
    const data = await resp.json();
    setSessionId(data.session_id);
    localStorage.setItem(STORAGE_KEY, data.session_id);
    return data.session_id;
  }, []);

  const clearSession = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    localStorage.removeItem(STORAGE_KEY);
    setSessionId(null);
    setMessages([]);
    setStatus("idle");
  }, []);

  const sendMessage = useCallback(
    async (content: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        let sid = sessionId;
        if (!sid) {
          sid = await createSession(controller.signal);
        }

        const userMsg: ChatMessage = { id: generateId(), role: "user", content };
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
          signal: controller.signal,
        });

        const handlers = createSSEHandlers(assistantId, setMessages, setStatus);

        if (!response.ok) {
          const errBody = await response.json().catch(() => ({ detail: "Request failed" }));
          handlers.onError(errBody.detail || `HTTP ${response.status}`);
          return;
        }

        await readSSEStream(response, handlers, controller.signal);
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          setStatus("idle");
          return;
        }
        setStatus("error");
      }
    },
    [sessionId, createSession]
  );

  const approveToolCall = useCallback(
    async (approved: boolean) => {
      if (!sessionId) return;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
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
            signal: controller.signal,
          }
        );

        const handlers = createSSEHandlers(assistantId, setMessages, setStatus);

        if (!response.ok) {
          const errBody = await response.json().catch(() => ({ detail: "Request failed" }));
          handlers.onError(errBody.detail || `HTTP ${response.status}`);
          return;
        }

        await readSSEStream(response, handlers, controller.signal);
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          setStatus("idle");
          return;
        }
        setStatus("error");
      }
    },
    [sessionId]
  );

  // Abort in-flight requests on unmount
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  return { messages, status, sendMessage, approveToolCall, clearSession };
}
