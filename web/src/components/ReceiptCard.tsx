"use client";

import type { Receipt } from "../types";

interface Props {
  receipt: Receipt;
}

export function ReceiptCard({ receipt }: Props) {
  return (
    <div className="rounded-lg border border-green-200 bg-green-50 p-4">
      <h3 className="text-sm font-semibold text-green-800">Receipt</h3>
      <div className="mt-2 space-y-1 text-sm text-green-700">
        <div className="flex justify-between">
          <span>Product</span>
          <span className="font-medium">{receipt.product_name}</span>
        </div>
        <div className="flex justify-between">
          <span>Price</span>
          <span className="font-medium">
            ${receipt.price.toFixed(2)} {receipt.currency}
          </span>
        </div>
        {receipt.average_rating != null && (
          <div className="flex justify-between">
            <span>Rating</span>
            <span className="font-medium">{receipt.average_rating}/5</span>
          </div>
        )}
        {receipt.price_range && (
          <div className="flex justify-between">
            <span>Price Range</span>
            <span className="font-medium">{receipt.price_range}</span>
          </div>
        )}
        {receipt.recommendation_reason && (
          <p className="mt-2 text-xs text-green-600 italic">
            {receipt.recommendation_reason}
          </p>
        )}
      </div>
    </div>
  );
}
