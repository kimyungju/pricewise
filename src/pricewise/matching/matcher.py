"""ProductMatcher: same-product likelihood between a query and listings.

Wraps the frozen sentence encoder + trained MatchHead for inference inside
the agent's tools. Everything is lazy-loaded so importing the tools module
costs nothing when matching is disabled; a missing weights file raises
MatcherUnavailable, which callers treat as "matching off".
"""

from __future__ import annotations

import logging
from pathlib import Path

import torch

from pricewise.matching.model import MatchHead
from pricewise.matching.train import EMBED_DIM, ENCODER_MODEL, WEIGHTS_PATH

logger = logging.getLogger(__name__)


class MatcherUnavailable(RuntimeError):
    """Raised when the matcher cannot run (no trained weights, no encoder)."""


class ProductMatcher:
    def __init__(
        self,
        head: MatchHead | None = None,
        weights_path: Path = WEIGHTS_PATH,
        embed_dim: int = EMBED_DIM,
        hidden_dim: int = 256,
    ) -> None:
        self._head = head
        self._weights_path = Path(weights_path)
        self._embed_dim = embed_dim
        self._hidden_dim = hidden_dim
        self._encoder = None

    def _get_head(self) -> MatchHead:
        if self._head is None:
            if not self._weights_path.exists():
                raise MatcherUnavailable(
                    f"no trained weights at {self._weights_path}; "
                    "run `python -m pricewise.matching.train` first"
                )
            head = MatchHead(embed_dim=self._embed_dim, hidden_dim=self._hidden_dim)
            head.load_state_dict(
                torch.load(self._weights_path, map_location="cpu", weights_only=True)
            )
            head.eval()
            self._head = head
        return self._head

    def _embed(self, texts: list[str]) -> torch.Tensor:
        """Encode texts to embedding tensors. Mockable seam for tests."""
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading sentence encoder: %s", ENCODER_MODEL)
            self._encoder = SentenceTransformer(ENCODER_MODEL, device="cpu")
        return self._encoder.encode(
            texts, convert_to_tensor=True, show_progress_bar=False
        ).float()

    def score(self, query: str, candidates: list[str]) -> list[float]:
        """Same-product probability in [0, 1] for each candidate listing."""
        if not candidates:
            return []
        head = self._get_head()
        embeddings = self._embed([query, *candidates])
        query_emb = embeddings[0].unsqueeze(0).expand(len(candidates), -1)
        cand_emb = embeddings[1:]
        with torch.no_grad():
            probs = torch.sigmoid(head(query_emb, cand_emb))
        return [float(p) for p in probs]


# Module-level singleton, created lazily by callers
_matcher: ProductMatcher | None = None


def get_matcher() -> ProductMatcher:
    global _matcher
    if _matcher is None:
        _matcher = ProductMatcher()
    return _matcher
