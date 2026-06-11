"""Tests for the matcher training loop (synthetic embeddings, no encoder)."""

import torch

from pricewise.matching.train import auc_score, evaluate, train_head


def _separable_dataset(n: int, dim: int, seed: int):
    """Pos pairs = nearly identical vectors; neg pairs = independent ones."""
    g = torch.Generator().manual_seed(seed)
    half = n // 2
    base = torch.randn(half, dim, generator=g)
    e1 = torch.cat([base, torch.randn(half, dim, generator=g)])
    e2 = torch.cat([base + 0.05 * torch.randn(half, dim, generator=g),
                    torch.randn(half, dim, generator=g)])
    y = torch.cat([torch.ones(half), torch.zeros(half)])
    return e1, e2, y


class TestAUC:
    def test_perfect_ranking(self):
        assert auc_score([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0]) == 1.0

    def test_known_partial_ranking(self):
        # classic example: one of four pos/neg orderings inverted -> 0.75
        assert auc_score([0.1, 0.4, 0.35, 0.8], [0, 0, 1, 1]) == 0.75

    def test_reversed_ranking_is_zero(self):
        assert auc_score([0.1, 0.2, 0.8, 0.9], [1, 1, 0, 0]) == 0.0

    def test_single_class_returns_none(self):
        assert auc_score([0.5, 0.6], [1, 1]) is None


class TestTrainHead:
    def test_learns_separable_data(self):
        train = _separable_dataset(256, 32, seed=0)
        val = _separable_dataset(64, 32, seed=1)
        head, history = train_head(
            train, val, embed_dim=32, hidden_dim=16,
            epochs=20, lr=0.01, batch_size=32, seed=0,
        )
        metrics = evaluate(head, val)
        assert metrics["accuracy"] >= 0.9
        assert metrics["auc"] >= 0.95

    def test_history_records_epochs(self):
        train = _separable_dataset(64, 16, seed=2)
        val = _separable_dataset(32, 16, seed=3)
        _head, history = train_head(
            train, val, embed_dim=16, hidden_dim=8,
            epochs=3, lr=0.01, batch_size=16, seed=0,
        )
        assert len(history) == 3
        for row in history:
            assert "train_loss" in row and "val_loss" in row and "val_auc" in row

    def test_extra_features_are_learned_when_provided(self):
        """Embeddings identical for every pair; labels depend ONLY on the
        extra features — the head must learn from them."""
        g = torch.Generator().manual_seed(5)
        n, dim = 128, 8
        e = torch.randn(n, dim, generator=g)
        y = torch.cat([torch.ones(n // 2), torch.zeros(n // 2)])
        extra = torch.cat([torch.ones(n // 2, 3), torch.zeros(n // 2, 3)])
        data = (e, e.clone(), y, extra)

        head, _ = train_head(
            data, data, embed_dim=dim, hidden_dim=8,
            epochs=15, lr=0.02, batch_size=32, seed=0, extra_dim=3,
        )
        metrics = evaluate(head, data)
        assert metrics["accuracy"] >= 0.95

    def test_evaluate_returns_bounded_metrics(self):
        data = _separable_dataset(64, 16, seed=4)
        head, _ = train_head(
            data, data, embed_dim=16, hidden_dim=8,
            epochs=2, lr=0.01, batch_size=16, seed=0,
        )
        m = evaluate(head, data)
        for key in ("accuracy", "f1", "auc"):
            assert key in m
            assert 0.0 <= m[key] <= 1.0
