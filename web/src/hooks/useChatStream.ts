"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { z } from "zod";
import type { ChatMessage, ChatStatus } from "../types";
import { readSSEStream, ChatStreamError } from "../lib/chat-stream";
import { createSSEHandlers } from "../lib/chat-handlers";
import { sessionHistorySchema } from "../lib/chat-schema";

const API_BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL.replace(/\/+$/, "")}/chat`
  : "/api/chat";
const STORAGE_KEY = "pricewise_session_id";
const generateId = () => crypto.randomUUID();

type Request = { readonly kind: "message"; readonly content: string }
  | { readonly kind: "approval"; readonly approved: boolean };

async function responseError(response: Response): Promise<string> {
  try {
    const parsed = z.object({ detail: z.string() }).safeParse(await response.json());
    if (parsed.success) return parsed.data.detail;
  } catch (error) {
    if (!(error instanceof SyntaxError)) throw error;
  }
  return `Request failed (HTTP ${response.status}). Please try again.`;
}

export function useChatStream() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>("idle");
  const sessionRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const busyRef = useRef(false);

  const loadHistory = useCallback(async (sid: string, signal: AbortSignal) => {
    const response = await fetch(`${API_BASE}/sessions/${sid}/messages`, { signal });
    signal.throwIfAborted();
    if (response.status === 404) {
      localStorage.removeItem(STORAGE_KEY);
      sessionRef.current = null;
      setMessages([]);
      setStatus("idle");
      return;
    }
    if (!response.ok) throw new ChatStreamError(await responseError(response));
    const history = sessionHistorySchema.parse(await response.json());
    signal.throwIfAborted();
    const hydrated: ChatMessage[] = history.messages.map((message) => ({ ...message, id: message.id || generateId() }));
    if (history.receipt) {
      const last = hydrated.findLastIndex((message) => message.role === "assistant");
      if (last >= 0) hydrated[last] = { ...hydrated[last], receipt: history.receipt };
    }
    if (history.pending_approval) {
      const pending = history.pending_approval;
      // Internal research messages are intentionally absent from public history.
      hydrated.push({ id: generateId(), role: "assistant", content: "", toolCalls: pending.tool_calls,
        isApprovalRequired: true, interruptIds: pending.interrupt_ids });
    }
    setMessages(hydrated);
    setStatus(history.pending_approval ? "awaiting_approval" : "idle");
  }, []);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return;
    sessionRef.current = stored;
    const controller = new AbortController();
    abortRef.current = controller;
    busyRef.current = true;
    setStatus("streaming");
    void loadHistory(stored, controller.signal).catch((error: unknown) => {
      if (controller.signal.aborted) return;
      const detail = error instanceof ChatStreamError ? error.message : "Could not load this conversation. Refresh to retry.";
      setMessages([{ id: generateId(), role: "assistant", content: `Error: ${detail}` }]);
      setStatus("error");
    }).finally(() => {
      if (abortRef.current === controller) { busyRef.current = false; abortRef.current = null; }
    });
    return () => controller.abort();
  }, [loadHistory]);

  const clearSession = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    busyRef.current = false;
    localStorage.removeItem(STORAGE_KEY);
    sessionRef.current = null;
    setMessages([]);
    setStatus("idle");
  }, []);

  const runRequest = useCallback(async (request: Request) => {
    if (busyRef.current) return;
    const pending = messages.findLast((message) => message.isApprovalRequired);
    if (request.kind === "message" && (!request.content.trim() || pending)) return;
    if (request.kind === "approval" && (!sessionRef.current || !pending)) return;
    busyRef.current = true;
    const controller = new AbortController();
    abortRef.current = controller;
    const assistantId = generateId();
    let refreshedHistory = false;
    const handlers = createSSEHandlers(assistantId, setMessages, setStatus);
    setStatus("streaming");
    setMessages((prev) => [
      ...prev.map((m) => request.kind === "approval" && m.isApprovalRequired ? { ...m, isApprovalRequired: false } : m),
      ...(request.kind === "message" ? [{ id: generateId(), role: "user" as const, content: request.content }] : []),
      { id: assistantId, role: "assistant", content: "", isStreaming: true },
    ]);
    try {
      let sid = sessionRef.current;
      if (!sid) {
        const response = await fetch(`${API_BASE}/sessions`, { method: "POST", signal: controller.signal });
        if (!response.ok) throw new ChatStreamError(await responseError(response));
        const created = z.object({ session_id: z.string().min(1) }).parse(await response.json());
        controller.signal.throwIfAborted();
        sid = created.session_id;
        sessionRef.current = sid;
        localStorage.setItem(STORAGE_KEY, sid);
      }
      const path = request.kind === "message" ? "messages" : "approve";
      const body = request.kind === "message" ? { content: request.content }
        : { approved: request.approved, interrupt_ids: pending?.interruptIds };
      const response = await fetch(`${API_BASE}/sessions/${sid}/${path}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body), signal: controller.signal,
      });
      controller.signal.throwIfAborted();
      if (!response.ok) {
        const detail = await responseError(response);
        if (response.status === 409) {
          await loadHistory(sid, controller.signal);
          refreshedHistory = true;
          setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "" }]);
        }
        throw new ChatStreamError(detail);
      }
      await readSSEStream(response, handlers, controller.signal);
    } catch (error) {
      if (controller.signal.aborted) return;
      if (request.kind === "approval" && pending && !refreshedHistory) {
        // Keep retry available after transport failure. The server verifies interrupt IDs.
        setMessages((prev) => prev.map((m) => m.id === pending.id ? { ...m, isApprovalRequired: true } : m));
        setStatus("awaiting_approval");
      }
      handlers.onError(error instanceof ChatStreamError ? error.message : "Could not complete the request. Please try again.");
    } finally {
      if (abortRef.current === controller) { busyRef.current = false; abortRef.current = null; }
    }
  }, [messages, loadHistory]);

  const sendMessage = useCallback((content: string) => runRequest({ kind: "message", content }), [runRequest]);
  const approveToolCall = useCallback((approved: boolean) => runRequest({ kind: "approval", approved }), [runRequest]);
  useEffect(() => () => abortRef.current?.abort(), []);
  return { messages, status, sendMessage, approveToolCall, clearSession };
}
