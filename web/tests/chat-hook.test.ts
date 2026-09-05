// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useChatStream } from "../src/hooks/useChatStream";

afterEach(() => { cleanup(); localStorage.clear(); vi.unstubAllGlobals(); });
const stored = "saved-session";
const history = { messages: [{ id: "user", role: "user", content: "Find shoes" }], pending_approval: {
  tool_calls: [{ id: "tool-one", name: "search_product", args: { query: "shoes" } }], interrupt_ids: ["approval-one"],
} };

it("restores pending approval after refresh", async () => {
  // Given a saved session interrupted at approval.
  localStorage.setItem("pricewise_session_id", stored);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(history)));
  // When the hook loads its history.
  const { result } = renderHook(() => useChatStream());
  // Then the approval remains actionable and normal messages remain blocked.
  await waitFor(() => expect(result.current.status).toBe("awaiting_approval"));
  expect(result.current.messages.at(-1)?.isApprovalRequired).toBe(true);
});

it("preserves a saved session when history temporarily fails", async () => {
  localStorage.setItem("pricewise_session_id", stored);
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
  const { result } = renderHook(() => useChatStream());
  await waitFor(() => expect(result.current.status).toBe("error"));
  expect(localStorage.getItem("pricewise_session_id")).toBe(stored);
  expect(result.current.messages.at(-1)?.content).not.toBe("");
});

it("finishes the composing message visibly when sending fails", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(Response.json({ session_id: stored }))
    .mockRejectedValueOnce(new TypeError("offline")));
  const { result } = renderHook(() => useChatStream());
  await act(async () => result.current.sendMessage("shoes"));
  expect(result.current.status).toBe("error");
  expect(result.current.messages.at(-1)?.isStreaming).toBe(false);
  expect(result.current.messages.at(-1)?.content).toContain("Error:");
});

it("does not let delayed history overwrite a new chat", async () => {
  localStorage.setItem("pricewise_session_id", stored);
  let resolveHistory: (value: Response) => void = () => undefined;
  vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise<Response>((resolve) => { resolveHistory = resolve; })));
  const { result } = renderHook(() => useChatStream());
  await act(async () => { result.current.clearSession(); resolveHistory(Response.json(history)); });
  expect(result.current.messages).toEqual([]);
  expect(result.current.status).toBe("idle");
});

it("sends the stored interrupt ID and completes the previous approval card", async () => {
  localStorage.setItem("pricewise_session_id", stored);
  const sse = 'event: tool_result\ndata: {"id":"tool-one","name":"search_product","result":"found"}\n\nevent: token\ndata: {"content":"Result"}\n\nevent: done\ndata: {}\n\n';
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json(history)).mockResolvedValueOnce(new Response(sse));
  vi.stubGlobal("fetch", fetcher);
  const { result } = renderHook(() => useChatStream());
  await waitFor(() => expect(result.current.status).toBe("awaiting_approval"));
  await act(async () => result.current.approveToolCall(true));
  expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ approved: true, interrupt_ids: ["approval-one"] });
  expect(result.current.messages.find((m) => m.toolCalls)?.toolCalls?.[0].result).toBe("found");
  expect(result.current.status).toBe("idle");
});

it("prevents duplicate submissions while session creation is still pending", async () => {
  let resolveSession: (value: Response) => void = () => undefined;
  const fetcher = vi.fn().mockReturnValueOnce(new Promise<Response>((resolve) => { resolveSession = resolve; }))
    .mockResolvedValueOnce(new Response('event: token\ndata: {"content":"hello"}\n\nevent: done\ndata: {}\n\n'));
  vi.stubGlobal("fetch", fetcher);
  const { result } = renderHook(() => useChatStream());
  await act(async () => {
    const first = result.current.sendMessage("hello");
    const duplicate = result.current.sendMessage("hello");
    resolveSession(Response.json({ session_id: stored }));
    await Promise.all([first, duplicate]);
  });
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(result.current.messages.filter((m) => m.role === "user")).toHaveLength(1);
});

it("refreshes stale approval state on409 without retrying an action", async () => {
  localStorage.setItem("pricewise_session_id", stored);
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json(history))
    .mockResolvedValueOnce(Response.json({ detail: "Approval expired" }, { status: 409 }))
    .mockResolvedValueOnce(Response.json({ messages: history.messages, pending_approval: null }));
  vi.stubGlobal("fetch", fetcher);
  const { result } = renderHook(() => useChatStream());
  await waitFor(() => expect(result.current.status).toBe("awaiting_approval"));
  await act(async () => result.current.approveToolCall(true));
  expect(result.current.messages.some((m) => m.isApprovalRequired)).toBe(false);
  expect(result.current.messages.at(-1)?.content).toContain("Approval expired");
  expect(fetcher).toHaveBeenCalledTimes(3);
});

it("keeps approval retry actionable after a transport failure", async () => {
  localStorage.setItem("pricewise_session_id", stored);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(Response.json(history)).mockRejectedValueOnce(new TypeError("offline")));
  const { result } = renderHook(() => useChatStream());
  await waitFor(() => expect(result.current.status).toBe("awaiting_approval"));
  await act(async () => result.current.approveToolCall(true));
  expect(result.current.status).toBe("awaiting_approval");
  expect(result.current.messages.some((m) => m.isApprovalRequired)).toBe(true);
  expect(result.current.messages.at(-1)?.content).toContain("Error:");
});
