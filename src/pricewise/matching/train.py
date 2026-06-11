"""Training loop for the same-product MatchHead (PyTorch, CPU).

The sentence encoder (all-MiniLM-L6-v2) stays frozen; titles are embedded
once up front, so the trainable surface is just the MLP head — a few
hundred KB of weights that train in seconds on CPU.

Run end-to-end (generates data, embeds, trains, evaluates, saves):

    uv run python -m pricewise.matching.train
"""

from __future__ import annotations

import json
from pathlib import Path

import torch
from torch import nn

from pricewise.matching.model import MatchHead

WEIGHTS_DIR = Path(__file__).parent / "weights"
WEIGHTS_PATH = WEIGHTS_DIR / "match_head.pt"
METRICS_PATH = WEIGHTS_DIR / "metrics.json"

ENCODER_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384


def auc_score(scores, labels) -> float | None:
    """ROC AUC via the rank statistic (probability a random positive
    outranks a random negative). Pure Python — no sklearn dependency."""
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return None
    wins = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return wins / (len(pos) * len(neg))


def _unpack(data: tuple):
    """(e1, e2, y) or (e1, e2, y, extra) -> e1, e2, y, extra|None."""
    if len(data) == 4:
        return data[0], data[1], data[2], data[3]
    e1, e2, y = data
    return e1, e2, y, None


def evaluate(head: MatchHead, data: tuple) -> dict:
    """Accuracy / F1 / AUC of a trained head on (e1, e2, labels[, extra])."""
    e1, e2, y, extra = _unpack(data)
    head.eval()
    with torch.no_grad():
        probs = torch.sigmoid(head(e1, e2, extra))
    preds = (probs >= 0.5).float()

    tp = float(((preds == 1) & (y == 1)).sum())
    fp = float(((preds == 1) & (y == 0)).sum())
    fn = float(((preds == 0) & (y == 1)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return {
        "accuracy": float((preds == y).float().mean()),
        "f1": f1,
        "auc": auc_score(probs.tolist(), y.tolist()) or 0.0,
        "n": int(y.numel()),
    }


def train_head(
    train_data: tuple,
    val_data: tuple,
    embed_dim: int = EMBED_DIM,
    hidden_dim: int = 256,
    epochs: int = 30,
    lr: float = 1e-3,
    batch_size: int = 64,
    seed: int = 0,
    extra_dim: int = 0,
) -> tuple[MatchHead, list[dict]]:
    """Train a MatchHead with BCE loss + Adam; keep the best-val-AUC state."""
    torch.manual_seed(seed)
    head = MatchHead(embed_dim=embed_dim, hidden_dim=hidden_dim, extra_dim=extra_dim)
    optimizer = torch.optim.Adam(head.parameters(), lr=lr)
    loss_fn = nn.BCEWithLogitsLoss()

    e1, e2, y, extra = _unpack(train_data)
    val_e1, val_e2, val_y, val_extra = _unpack(val_data)
    n = y.numel()
    history: list[dict] = []
    best_auc, best_state = -1.0, None

    for epoch in range(epochs):
        head.train()
        perm = torch.randperm(n)
        epoch_loss = 0.0
        for start in range(0, n, batch_size):
            idx = perm[start:start + batch_size]
            optimizer.zero_grad()
            logits = head(
                e1[idx], e2[idx], extra[idx] if extra is not None else None
            )
            loss = loss_fn(logits, y[idx])
            loss.backward()
            optimizer.step()
            epoch_loss += float(loss.detach()) * idx.numel()

        head.eval()
        with torch.no_grad():
            val_logits = head(val_e1, val_e2, val_extra)
            val_loss = float(loss_fn(val_logits, val_y))
            val_auc = auc_score(
                torch.sigmoid(val_logits).tolist(), val_y.tolist()
            ) or 0.0

        history.append({
            "epoch": epoch + 1,
            "train_loss": epoch_loss / n,
            "val_loss": val_loss,
            "val_auc": val_auc,
        })
        if val_auc > best_auc:
            best_auc = val_auc
            best_state = {k: v.clone() for k, v in head.state_dict().items()}

    if best_state is not None:
        head.load_state_dict(best_state)
    return head, history


def _featurize(pairs: list[dict], encoder) -> tuple:
    """Embed each unique title once, then assemble pair tensors (+ extras)."""
    from pricewise.matching.features import pair_features

    texts = sorted({p["text_a"] for p in pairs} | {p["text_b"] for p in pairs})
    embeddings = encoder.encode(texts, convert_to_tensor=True, show_progress_bar=False)
    index = {t: i for i, t in enumerate(texts)}
    e1 = torch.stack([embeddings[index[p["text_a"]]] for p in pairs])
    e2 = torch.stack([embeddings[index[p["text_b"]]] for p in pairs])
    y = torch.tensor([float(p["label"]) for p in pairs])
    extra = torch.tensor(
        [pair_features(p["text_a"], p["text_b"]) for p in pairs], dtype=torch.float32
    )
    return e1.float(), e2.float(), y, extra


def main() -> None:
    from sentence_transformers import SentenceTransformer

    from pricewise.matching.data import CATALOG, generate_pairs, split_catalog

    train_cat, val_cat, test_cat = split_catalog(CATALOG, seed=7)
    train_pairs = generate_pairs(train_cat, n_pairs=3000, seed=11)
    val_pairs = generate_pairs(val_cat, n_pairs=600, seed=12)
    test_pairs = generate_pairs(test_cat, n_pairs=600, seed=13)
    print(f"pairs: train={len(train_pairs)} val={len(val_pairs)} test={len(test_pairs)}")
    print(f"products: train={len(train_cat)} val={len(val_cat)} test={len(test_cat)}")

    encoder = SentenceTransformer(ENCODER_MODEL, device="cpu")
    train_data = _featurize(train_pairs, encoder)
    val_data = _featurize(val_pairs, encoder)
    test_data = _featurize(test_pairs, encoder)

    from pricewise.matching.features import EXTRA_DIM

    head, history = train_head(train_data, val_data, extra_dim=EXTRA_DIM)
    for row in history[-3:]:
        print(f"epoch {row['epoch']:3d} train_loss={row['train_loss']:.4f} "
              f"val_loss={row['val_loss']:.4f} val_auc={row['val_auc']:.4f}")

    metrics = {
        "val": evaluate(head, val_data),
        "test": evaluate(head, test_data),
        "train_pairs": len(train_pairs),
        "encoder": ENCODER_MODEL,
        "best_val_auc": max(r["val_auc"] for r in history),
    }
    print("test:", metrics["test"])

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(head.state_dict(), WEIGHTS_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"saved {WEIGHTS_PATH} and {METRICS_PATH}")


if __name__ == "__main__":
    main()
