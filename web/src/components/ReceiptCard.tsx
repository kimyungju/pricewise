"use client";

import type { Receipt } from "../types";

interface Props {
  receipt: Receipt;
}

function StarRating({ rating }: { rating: number }) {
  const full = Math.floor(rating);
  const hasHalf = rating - full >= 0.3;
  const stars = [];

  for (let i = 0; i < 5; i++) {
    if (i < full) {
      stars.push(
        <svg key={i} className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="var(--accent)">
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      );
    } else if (i === full && hasHalf) {
      stars.push(
        <svg key={i} className="h-3.5 w-3.5" viewBox="0 0 20 20">
          <defs>
            <linearGradient id={`half-${i}`}>
              <stop offset="50%" stopColor="var(--accent)" />
              <stop offset="50%" stopColor="#e8e2da" />
            </linearGradient>
          </defs>
          <path fill={`url(#half-${i})`} d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      );
    } else {
      stars.push(
        <svg key={i} className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="#e8e2da">
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      );
    }
  }

  return <div className="flex items-center gap-0.5">{stars}</div>;
}

export function ReceiptCard({ receipt }: Props) {
  return (
    <div
      className="overflow-hidden rounded-xl"
      style={{ border: '1px solid var(--border)', background: 'var(--bg-chat)', boxShadow: 'var(--shadow-md)' }}
    >
      {/* Header accent bar */}
      <div className="h-1" style={{ background: 'linear-gradient(90deg, var(--accent), #e8a76e)' }} />

      <div className="p-4">
        {/* Product name */}
        <h3
          className="text-base font-semibold tracking-tight"
          style={{ fontFamily: "'DM Serif Display', Georgia, serif", color: 'var(--text-primary)' }}
        >
          {receipt.product_name}
        </h3>

        {/* Rating */}
        {receipt.average_rating != null && (
          <div className="mt-1.5 flex items-center gap-2">
            <StarRating rating={receipt.average_rating} />
            <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
              {receipt.average_rating}
            </span>
          </div>
        )}

        {/* Divider */}
        <div className="my-3" style={{ borderTop: '1px solid var(--border-light)' }} />

        {/* Price section */}
        <div className="flex items-baseline justify-between">
          <span className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
            Price
          </span>
          <span
            className="text-xl font-bold tabular-nums"
            style={{ color: 'var(--accent)' }}
          >
            ${receipt.price.toFixed(2)}
            <span className="ml-1 text-xs font-normal" style={{ color: 'var(--text-muted)' }}>
              {receipt.currency}
            </span>
          </span>
        </div>

        {/* Price range */}
        {receipt.price_range && (
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
              Range
            </span>
            <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
              {receipt.price_range}
            </span>
          </div>
        )}

        {/* Recommendation */}
        {receipt.recommendation_reason && (
          <div
            className="mt-3 rounded-lg p-3 text-xs leading-relaxed"
            style={{ background: 'var(--accent-soft)', color: 'var(--text-secondary)' }}
          >
            {receipt.recommendation_reason}
          </div>
        )}
      </div>
    </div>
  );
}
