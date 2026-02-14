export type MessageRole = "user" | "assistant";

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
}

export interface Receipt {
  product_name: string;
  price: number;
  currency: string;
  average_rating?: number | null;
  price_range?: string | null;
  recommendation_reason?: string | null;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  toolCalls?: ToolCall[];
  receipt?: Receipt;
  isStreaming?: boolean;
  isApprovalRequired?: boolean;
}

export type ChatStatus = "idle" | "streaming" | "awaiting_approval" | "error";
