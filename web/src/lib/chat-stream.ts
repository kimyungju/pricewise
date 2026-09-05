import { z } from "zod";
import type { Receipt, ToolCall } from "../types";
import { approvalSchema, receiptSchema, toolCallSchema } from "./chat-schema";

export type StreamHandlers = {
  readonly onToken: (content: string) => void;
  readonly onApprovalRequired: (calls: ToolCall[], interruptIds?: string[]) => void;
  readonly onReceipt: (receipt: Receipt) => void;
  readonly onToolCall: (call: ToolCall) => void;
  readonly onToolResult: (name: string, result: string, id?: string) => void;
  readonly onDone: () => void;
  readonly onError: (message: string) => void;
};

export class ChatStreamError extends Error {}

function dispatch(event: string, json: string, handlers: StreamHandlers): void {
  const data: unknown = JSON.parse(json);
  switch (event) {
    case "token":
      handlers.onToken(z.object({ content: z.string() }).parse(data).content); break;
    case "tool_call": handlers.onToolCall(toolCallSchema.parse(data)); break;
    case "tool_result": {
      const result = z.object({ name: z.string(), result: z.string(), id: z.string().optional() }).parse(data);
      handlers.onToolResult(result.name, result.result, result.id); break;
    }
    case "approval_required": {
      const approval = approvalSchema.parse(data);
      handlers.onApprovalRequired(approval.tool_calls, approval.interrupt_ids); break;
    }
    case "receipt": handlers.onReceipt(receiptSchema.parse(data)); break;
    case "error": handlers.onError(z.object({ message: z.string() }).parse(data).message); break;
    case "done": handlers.onDone(); break;
  }
}

export async function readSSEStream(response: Response, handlers: StreamHandlers, signal?: AbortSignal): Promise<void> {
  if (!response.body) throw new ChatStreamError("The server returned an empty response. Please try again.");
  signal?.throwIfAborted();
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  // Event state belongs to the SSE frame, never to a network chunk.
  let buffer = "";
  let event = "";
  let data: string[] = [];
  let completed = false;
  const abort = () => { void reader.cancel().catch(() => undefined); };
  signal?.addEventListener("abort", abort, { once: true });
  function consumeLine(line: string) {
    if (line === "") {
      if (data.length) {
        dispatch(event, data.join("\n"), handlers);
        if (event === "done") completed = true;
      }
      event = "";
      data = [];
      return;
    }
    const colon = line.indexOf(":");
    const field = colon < 0 ? line : line.slice(0, colon);
    const value = colon < 0 ? "" : line.slice(colon + 1).replace(/^ /, "");
    if (field === "event") event = value;
    if (field === "data") data.push(value);
  }
  try {
    while (!completed) {
      const next = await reader.read();
      signal?.throwIfAborted();
      buffer += next.done ? decoder.decode() : decoder.decode(next.value, { stream: true });
      let newline = buffer.indexOf("\n");
      while (newline >= 0 && !completed) {
        consumeLine(buffer.slice(0, newline).replace(/\r$/, ""));
        buffer = buffer.slice(newline + 1);
        newline = buffer.indexOf("\n");
      }
      if (next.done) break;
    }
    if (!completed) throw new ChatStreamError("The connection ended before the response finished. Please try again.");
  } catch (error) {
    if (signal?.aborted) throw signal.reason;
    if (error instanceof ChatStreamError) throw error;
    throw new ChatStreamError("The response could not be read. Please try again.", { cause: error });
  } finally {
    signal?.removeEventListener("abort", abort);
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
