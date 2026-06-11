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
    def __init__(self, embed_dim: int = 384, hidden_dim: int = 256, dropout: float = 0.2):
        super().__init__()
        self.embed_dim = embed_dim
        self.net = nn.Sequential(
            nn.Linear(4 * embed_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, e1: torch.Tensor, e2: torch.Tensor) -> torch.Tensor:
        """(B, d), (B, d) -> (B,) match logits."""
        features = torch.cat([e1, e2, torch.abs(e1 - e2), e1 * e2], dim=-1)
        return self.net(features).squeeze(-1)
