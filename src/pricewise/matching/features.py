"""Handcrafted pair features for the same-product matcher.

Error analysis on the embedding-only baseline (test AUC 0.79) showed the
dominant failure mode is numeric variant confusion: "LG C4 55-inch" vs
"LG C4 65-inch" or "XM5" vs "XM4" produce nearly identical sentence
embeddings, so |e1-e2| cannot separate a sibling variant from harmless
surface variation. Numbers are the variant signal retailers actually use,
so we extract them symbolically and let the MLP weigh them against the
embedding features.
"""

from __future__ import annotations

import re

EXTRA_DIM = 3

_NUM_RE = re.compile(r"\d+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Prices ("$249", "$1,299.00") are listing noise, not variant numbers.
_PRICE_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    return set(_NUM_RE.findall(_PRICE_RE.sub(" ", text)))


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def pair_features(text_a: str, text_b: str) -> list[float]:
    """[numeric jaccard, numeric set equality, token jaccard] in [0, 1].

    Noise tolerance is the MLP's job: a "2026 NEW ..." prefix or a
    "128GB" spec adds spurious numbers, so these are signals, not rules.
    """
    na, nb = _numbers(text_a), _numbers(text_b)
    if na or nb:
        num_jaccard = len(na & nb) / len(na | nb)
        num_equal = 1.0 if na == nb else 0.0
    else:
        num_jaccard = 1.0
        num_equal = 1.0

    ta, tb = _tokens(text_a), _tokens(text_b)
    tok_jaccard = len(ta & tb) / len(ta | tb) if (ta | tb) else 1.0

    return [num_jaccard, num_equal, tok_jaccard]
