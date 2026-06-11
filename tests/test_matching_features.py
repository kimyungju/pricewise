"""Tests for handcrafted pair features (numeric variant signals)."""

from pricewise.matching.features import EXTRA_DIM, pair_features


def test_returns_fixed_dimension():
    feats = pair_features("LG C4 55 inch", "LG C4 65 inch")
    assert len(feats) == EXTRA_DIM


def test_numeric_mismatch_detected():
    same = pair_features("Sony WH-1000XM5", "Sony 1000XM5 Headphones")
    diff = pair_features("Sony WH-1000XM5", "Sony WH-1000XM4")
    # numeric equality indicator: 1.0 when number sets match, 0.0 when not
    assert same[1] == 1.0
    assert diff[1] == 0.0


def test_inch_variant_mismatch():
    feats = pair_features("LG C4 OLED 55-inch TV", "LG C4 OLED 65-inch TV")
    assert feats[0] < 1.0  # numeric jaccard penalized
    assert feats[1] == 0.0


def test_no_numbers_counts_as_match():
    feats = pair_features("AirPods Max", "Apple AirPods Max Silver")
    assert feats[0] == 1.0
    assert feats[1] == 1.0


def test_token_jaccard_bounds():
    identical = pair_features("iPhone 15 Pro", "iPhone 15 Pro")
    disjoint = pair_features("iPhone 15 Pro", "Dyson Vacuum")
    assert identical[2] == 1.0
    assert 0.0 <= disjoint[2] < 0.3


def test_prices_are_not_variant_numbers():
    """Real listings carry prices ("- $249 at Amazon"); a price is not a
    model/variant number and must not trigger the mismatch penalty."""
    feats = pair_features("AirPods Pro 2", "AirPods Pro 2 - $249.99 at Amazon")
    assert feats[0] == 1.0
    assert feats[1] == 1.0


def test_values_all_bounded():
    feats = pair_features("2026 NEW iPhone 15 128GB", "iPhone 15")
    for f in feats:
        assert 0.0 <= f <= 1.0
