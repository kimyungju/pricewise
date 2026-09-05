export type MessageRole = "user" | "assistant";

export interface ToolCall {
  id?: string;
  name: string;
  args: Record<string, unknown>;
  result?: string;
}

export interface ProductSummary {
  product_name: string;
  price: number;
  currency: string;
  average_rating?: number | null;
  price_range?: string | null;
  pros?: string[];
  cons?: string[];
}

export interface Receipt {
  product_name: string;
  price: number;
  currency: string;
  average_rating?: number | null;
  price_range?: string | null;
  recommendation_reason?: string | null;
  comparison_products?: ProductSummary[] | null;
  comparison_summary?: string | null;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  toolCalls?: ToolCall[];
  receipt?: Receipt;
  isStreaming?: boolean;
  isApprovalRequired?: boolean;
  interruptIds?: string[];
}

export type ChatStatus = "idle" | "streaming" | "awaiting_approval" | "error";
