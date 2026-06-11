"""Tests for the MatchHead pair-classification module (pure PyTorch)."""

import torch

from pricewise.matching.model import MatchHead


def test_forward_returns_one_logit_per_pair():
    head = MatchHead(embed_dim=384)
    e1 = torch.randn(8, 384)
    e2 = torch.randn(8, 384)
    logits = head(e1, e2)
    assert logits.shape == (8,)


def test_gradients_flow_to_all_parameters():
    head = MatchHead(embed_dim=384)
    e1 = torch.randn(4, 384)
    e2 = torch.randn(4, 384)
    labels = torch.tensor([1.0, 0.0, 1.0, 0.0])
    loss = torch.nn.functional.binary_cross_entropy_with_logits(head(e1, e2), labels)
    loss.backward()
    for name, param in head.named_parameters():
        assert param.grad is not None, f"no gradient for {name}"
        assert torch.any(param.grad != 0), f"zero gradient for {name}"


def test_identical_embeddings_score_higher_than_random_after_one_step():
    """One optimization step on an obvious batch should move the model the
    right way — a minimal end-to-end sanity check of the training mechanics."""
    torch.manual_seed(0)
    head = MatchHead(embed_dim=32, hidden_dim=16)
    opt = torch.optim.Adam(head.parameters(), lr=0.05)

    same = torch.randn(64, 32)
    pos = (same, same + 0.01 * torch.randn(64, 32), torch.ones(64))
    neg = (torch.randn(64, 32), torch.randn(64, 32), torch.zeros(64))

    for _ in range(30):
        opt.zero_grad()
        e1 = torch.cat([pos[0], neg[0]])
        e2 = torch.cat([pos[1], neg[1]])
        y = torch.cat([pos[2], neg[2]])
        loss = torch.nn.functional.binary_cross_entropy_with_logits(head(e1, e2), y)
        loss.backward()
        opt.step()

    with torch.no_grad():
        v = torch.randn(1, 32)
        same_logit = head(v, v).item()
        diff_logit = head(v, -v).item()
    assert same_logit > diff_logit


def test_embed_dim_mismatch_raises():
    head = MatchHead(embed_dim=384)
    e1 = torch.randn(2, 128)
    e2 = torch.randn(2, 128)
    try:
        head(e1, e2)
        raised = False
    except RuntimeError:
        raised = True
    assert raised
