import { z } from "zod";

export const toolCallSchema = z.object({
  id: z.string().optional(), name: z.string(), args: z.record(z.string(), z.unknown()),
  result: z.string().optional(),
});
const productSchema = z.object({
  product_name: z.string(), price: z.number().finite(), currency: z.string(),
  average_rating: z.number().nullable().optional(), price_range: z.string().nullable().optional(),
  pros: z.array(z.string()).optional(), cons: z.array(z.string()).optional(),
});
export const receiptSchema = productSchema.extend({
  recommendation_reason: z.string().nullable().optional(),
  comparison_products: z.array(productSchema).nullable().optional(),
  comparison_summary: z.string().nullable().optional(),
});
export const approvalSchema = z.object({
  tool_calls: z.array(toolCallSchema).min(1), interrupt_ids: z.array(z.string()).optional(),
});
export const sessionHistorySchema = z.object({
  messages: z.array(z.object({
    id: z.string().optional(), role: z.enum(["user", "assistant"]), content: z.string(),
    toolCalls: z.array(toolCallSchema).optional(),
  })),
  receipt: receiptSchema.nullable().optional(),
  pending_approval: approvalSchema.nullable().optional(),
});
