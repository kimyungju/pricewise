"""Same-product pair classifier: a small PyTorch MLP head over frozen
sentence-embedding pair features.

Architecture (the classic SBERT pair-classification setup): given two
title embeddings e1, e2, build the feature vector

    [e1 ; e2 ; |e1 - e2| ; e1 * e2]        (4 x embed_dim)

and push it through a 2-layer MLP to a single logit. The absolute
difference and elementwise product capture symmetry ("how aligned are
these?") while the raw embeddings keep asymmetric information. The
sentence encoder stays frozen — only this head trains, which keeps the
whole training run on CPU in seconds.
"""

from __future__ import annotations

import torch
from torch import nn


class MatchHead(nn.Module):
    def __init__(
        self,
        embed_dim: int = 384,
        hidden_dim: int = 256,
        dropout: float = 0.2,
        extra_dim: int = 0,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.extra_dim = extra_dim
        self.net = nn.Sequential(
            nn.Linear(4 * embed_dim + extra_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
        )

    def forward(
        self,
        e1: torch.Tensor,
        e2: torch.Tensor,
        extra: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """(B, d), (B, d)[, (B, extra_dim)] -> (B,) match logits.

        `extra` carries symbolic pair features (numeric variant signals)
        that the frozen sentence embeddings cannot express — see
        features.py for why.
        """
        parts = [e1, e2, torch.abs(e1 - e2), e1 * e2]
        if extra is not None:
            parts.append(extra)
        features = torch.cat(parts, dim=-1)
        return self.net(features).squeeze(-1)
