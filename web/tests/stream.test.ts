import { describe, expect, it, vi } from "vitest";
import { readSSEStream } from "../src/lib/chat-stream";
import { createSSEHandlers } from "../src/lib/chat-handlers";
import type { ChatMessage, ChatStatus } from "../src/types";

function handlers() {
  return { onToken: vi.fn(), onToolCall: vi.fn(), onToolResult: vi.fn(),
    onApprovalRequired: vi.fn(), onReceipt: vi.fn(), onDone: vi.fn(), onError: vi.fn() };
}

function response(chunks: Uint8Array[]) {
  return new Response(new ReadableStream({ start(controller) {
    for (const chunk of chunks) controller.enqueue(chunk);
    controller.close();
  } }));
}

describe("SSE transport", () => {
  it("supports CRLF multiline frames delivered one byte at a time", async () => {
    const bytes = new TextEncoder().encode(': heartbeat\r\nevent:token\r\ndata: {"content":\r\ndata: "구두"}\r\n\r\nevent:done\r\ndata:{}\r\n\r\n');
    const events = handlers();
    await readSSEStream(response(Array.from(bytes, (byte) => new Uint8Array([byte]))), events);
    expect(events.onToken).toHaveBeenCalledExactlyOnceWith("구두");
    expect(events.onDone).toHaveBeenCalledOnce();
  });

  it.each(['event: token\ndata: not-json\n\n', 'event: token\ndata: {"content":null}\n\n',
    'event: approval_required\ndata: {"tool_calls":null}\n\n', 'event: token\ndata: {"content":"truncated'])
  ("rejects malformed or truncated payloads: %s", async (payload) => {
    const events = handlers();
    await expect(readSSEStream(response([new TextEncoder().encode(payload)]), events)).rejects.toThrow();
    expect(events.onDone).not.toHaveBeenCalled();
  });

  it("rejects an empty HTTP body", async () => {
    await expect(readSSEStream(new Response(null), handlers())).rejects.toThrow();
  });

  it("cancels an in-flight reader when aborted", async () => {
    const cancel = vi.fn();
    const stream = new ReadableStream<Uint8Array>({ cancel });
    const controller = new AbortController();
    const events = handlers();
    const reading = readSSEStream(new Response(stream), events, controller.signal);
    controller.abort();
    await expect(reading).rejects.toMatchObject({ name: "AbortError" });
    expect(cancel).toHaveBeenCalledOnce();
    expect(stream.locked).toBe(false);
    expect(events.onDone).not.toHaveBeenCalled();
  });
  it("preserves events at every byte boundary including Korean UTF-8", async () => {
    // Given an entire event stream and every possible network cut.
    const bytes = new TextEncoder().encode('event: token\ndata: {"content":"안녕하세요 👟"}\n\nevent: done\ndata: {}\n\n');
    for (let cut = 1; cut < bytes.length; cut++) {
      const events = handlers();
      // When separate chunks arrive.
      await readSSEStream(response([bytes.slice(0, cut), bytes.slice(cut)]), events);
      // Then event identity and Unicode survive the split.
      expect(events.onToken, `cut ${cut}`).toHaveBeenCalledWith("안녕하세요 👟");
      expect(events.onDone, `cut ${cut}`).toHaveBeenCalledOnce();
    }
  });

  it("reports a connection closed before done instead of silently succeeding", async () => {
    const events = handlers();
    const bytes = new TextEncoder().encode('event: token\ndata: {"content":"partial"}\n\n');
    await expect(readSSEStream(response([bytes]), events)).rejects.toThrow();
    expect(events.onDone).not.toHaveBeenCalled();
  });
});

function stateHarness(initial: ChatMessage[]) {
  let messages = initial;
  let status: ChatStatus = "streaming";
  const events = createSSEHandlers("current", (next) => { messages = typeof next === "function" ? next(messages) : next; },
    (next) => { status = typeof next === "function" ? next(status) : next; });
  return { events, messages: () => messages, status: () => status };
}

describe("stream state", () => {
  it("retains pending approval after terminal done", () => {
    const state = stateHarness([{ id: "current", role: "assistant", content: "" }]);
    state.events.onApprovalRequired([{ name: "search_product", args: {} }]);
    state.events.onDone();
    expect(state.status()).toBe("awaiting_approval");
  });

  it("retains error state and displays errors after partial output", () => {
    const state = stateHarness([{ id: "current", role: "assistant", content: "Partial answer" }]);
    state.events.onError("Connection failed");
    state.events.onDone();
    expect(state.status()).toBe("error");
    expect(state.messages()[0].content).toContain("Connection failed");
  });

  it("attaches a resumed result to the previous approval tool card", () => {
    const state = stateHarness([{ id: "previous", role: "assistant", content: "", toolCalls: [{ name: "search_product", args: {} }] },
      { id: "current", role: "assistant", content: "" }]);
    state.events.onToolResult("search_product", "found shoes");
    expect(state.messages()[0].toolCalls?.[0].result).toBe("found shoes");
  });

  it("correlates results by ID when multiple calls share the same name", () => {
    const state = stateHarness([{ id: "previous", role: "assistant", content: "", toolCalls: [
      { id: "first", name: "search_product", args: {} }, { id: "second", name: "search_product", args: {} },
    ] }, { id: "current", role: "assistant", content: "" }]);
    state.events.onToolResult("search_product", "first result", "first");
    expect(state.messages()[0].toolCalls?.[0].result).toBe("first result");
    expect(state.messages()[0].toolCalls?.[1].result).toBeUndefined();
  });
});

