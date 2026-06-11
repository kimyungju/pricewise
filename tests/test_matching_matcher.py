"""Tests for the ProductMatcher service (encoder and weights mocked)."""

from unittest.mock import patch

import pytest
import torch

from pricewise.matching.matcher import MatcherUnavailable, ProductMatcher
from pricewise.matching.model import MatchHead


def _trained_stub_head(dim: int = 8) -> MatchHead:
    """A tiny head trained just enough to rank identical above random."""
    torch.manual_seed(0)
    head = MatchHead(embed_dim=dim, hidden_dim=4)
    opt = torch.optim.Adam(head.parameters(), lr=0.05)
    base = torch.randn(64, dim)
    for _ in range(40):
        opt.zero_grad()
        e1 = torch.cat([base, torch.randn(64, dim)])
        e2 = torch.cat([base + 0.01 * torch.randn(64, dim), torch.randn(64, dim)])
        y = torch.cat([torch.ones(64), torch.zeros(64)])
        loss = torch.nn.functional.binary_cross_entropy_with_logits(head(e1, e2), y)
        loss.backward()
        opt.step()
    head.eval()
    return head


class TestProductMatcher:
    def test_scores_are_probabilities_one_per_candidate(self):
        matcher = ProductMatcher(head=_trained_stub_head(), embed_dim=8)
        fixed = {
            "query product": torch.ones(8),
            "candidate a": torch.ones(8),
            "candidate b": -torch.ones(8),
        }
        with patch.object(matcher, "_embed", side_effect=lambda texts: torch.stack([fixed[t] for t in texts])):
            scores = matcher.score("query product", ["candidate a", "candidate b"])
        assert len(scores) == 2
        assert all(0.0 <= s <= 1.0 for s in scores)
        # identical embedding should outrank the opposite one
        assert scores[0] > scores[1]

    def test_empty_candidates_returns_empty(self):
        matcher = ProductMatcher(head=_trained_stub_head(), embed_dim=8)
        with patch.object(matcher, "_embed") as mock_embed:
            assert matcher.score("q", []) == []
        mock_embed.assert_not_called()

    def test_missing_weights_raises_matcher_unavailable(self, tmp_path):
        matcher = ProductMatcher(weights_path=tmp_path / "nope.pt", embed_dim=8, extra_dim=0)
        with pytest.raises(MatcherUnavailable):
            matcher.score("q", ["a"])

    def test_score_passes_pair_features_for_extra_dim_head(self):
        from unittest.mock import MagicMock

        from pricewise.matching.features import pair_features

        spy = MagicMock()
        spy.extra_dim = 3
        spy.return_value = torch.tensor([0.0, 0.0])
        matcher = ProductMatcher(head=spy, embed_dim=8)
        with patch.object(matcher, "_embed", return_value=torch.zeros(3, 8)):
            matcher.score("LG C4 55 inch", ["LG C4 55-inch TV", "LG C4 65-inch TV"])

        extra = spy.call_args[0][2]
        assert extra.shape == (2, 3)
        expected_first = pair_features("LG C4 55 inch", "LG C4 55-inch TV")
        assert extra[0].tolist() == pytest.approx(expected_first)
        # the 65-inch sibling must show a numeric mismatch
        assert extra[1][1].item() == 0.0

    def test_loads_weights_from_file(self, tmp_path):
        trained = _trained_stub_head()
        path = tmp_path / "head.pt"
        torch.save(trained.state_dict(), path)

        matcher = ProductMatcher(weights_path=path, embed_dim=8, hidden_dim=4, extra_dim=0)
        fixed = {
            "q": torch.ones(8),
            "same": torch.ones(8),
            "diff": -torch.ones(8),
        }
        with patch.object(matcher, "_embed", side_effect=lambda texts: torch.stack([fixed[t] for t in texts])):
            scores = matcher.score("q", ["same", "diff"])
        assert scores[0] > scores[1]
