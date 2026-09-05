import type { Dispatch, SetStateAction } from "react";
import type { ChatMessage, ChatStatus } from "../types";
import type { StreamHandlers } from "./chat-stream";

export function createSSEHandlers(
  assistantId: string,
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>,
  setStatus: Dispatch<SetStateAction<ChatStatus>>,
): StreamHandlers {
  return {
    onToken: (token) => setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, content: m.content + token } : m)),
    onToolCall: (call) => setMessages((prev) => {
      if (call.id && prev.some((m) => m.toolCalls?.some((tc) => tc.id === call.id))) return prev;
      return prev.map((m) => m.id === assistantId ? { ...m, toolCalls: [...(m.toolCalls || []), call] } : m);
    }),
    onToolResult: (name, result, id) => setMessages((prev) => {
      const updated = [...prev];
      for (let i = updated.length - 1; i >= 0; i--) {
        const message = updated[i];
        const index = message.toolCalls?.findLastIndex((tc) => (id ? tc.id === id : tc.name === name) && tc.result === undefined) ?? -1;
        if (index >= 0 && message.toolCalls) {
          updated[i] = { ...message, toolCalls: message.toolCalls.map((tc, j) => j === index ? { ...tc, result } : tc) };
          break;
        }
      }
      return updated;
    }),
    onApprovalRequired: (toolCalls, interruptIds) => {
      setMessages((prev) => prev.map((m) => m.id === assistantId
        ? { ...m, isStreaming: false, isApprovalRequired: true, toolCalls, interruptIds } : m));
      setStatus("awaiting_approval");
    },
    onReceipt: (receipt) => setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, receipt } : m)),
    onDone: () => {
      setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, isStreaming: false } : m));
      setStatus((prev) => prev === "streaming" ? "idle" : prev);
    },
    onError: (message) => {
      setMessages((prev) => prev.map((m) => m.id === assistantId
        ? { ...m, content: `${m.content}${m.content ? "\n\n" : ""}Error: ${message}`, isStreaming: false } : m));
      setStatus((prev) => prev === "awaiting_approval" ? prev : "error");
    },
  };
}
