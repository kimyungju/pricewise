"""Tests for the synthetic product-pair dataset generator."""

from pricewise.matching.data import CATALOG, generate_pairs, split_catalog


def test_catalog_has_products_with_families():
    assert len(CATALOG) >= 40
    for p in CATALOG:
        assert p["id"] and p["brand"] and p["name"] and p["family"]


def test_generate_pairs_deterministic():
    a = generate_pairs(CATALOG, n_pairs=200, seed=42)
    b = generate_pairs(CATALOG, n_pairs=200, seed=42)
    assert a == b


def test_generate_pairs_different_seed_differs():
    a = generate_pairs(CATALOG, n_pairs=200, seed=42)
    b = generate_pairs(CATALOG, n_pairs=200, seed=43)
    assert a != b


def test_labels_roughly_balanced():
    pairs = generate_pairs(CATALOG, n_pairs=400, seed=0)
    pos_rate = sum(p["label"] for p in pairs) / len(pairs)
    assert 0.45 <= pos_rate <= 0.55


def test_positive_pairs_are_same_product():
    pairs = generate_pairs(CATALOG, n_pairs=400, seed=1)
    for p in pairs:
        if p["label"] == 1:
            assert p["product_a"] == p["product_b"]
        else:
            assert p["product_a"] != p["product_b"]


def test_positive_titles_differ_in_surface_form():
    pairs = generate_pairs(CATALOG, n_pairs=400, seed=2)
    positives = [p for p in pairs if p["label"] == 1]
    assert positives
    # at least 90% of positives must not be trivial identical strings
    differing = sum(1 for p in positives if p["text_a"] != p["text_b"])
    assert differing / len(positives) >= 0.9


def test_includes_hard_negatives_from_same_family():
    pairs = generate_pairs(CATALOG, n_pairs=400, seed=3)
    by_product = {p["id"]: p for p in CATALOG}
    hard = [
        p for p in pairs
        if p["label"] == 0
        and by_product[p["product_a"]]["family"] == by_product[p["product_b"]]["family"]
    ]
    # hard negatives are the point of the dataset — require a real share
    assert len(hard) >= 0.15 * sum(1 for p in pairs if p["label"] == 0)


def test_split_catalog_no_product_leakage():
    train, val, test = split_catalog(CATALOG, seed=7)
    train_ids = {p["id"] for p in train}
    val_ids = {p["id"] for p in val}
    test_ids = {p["id"] for p in test}
    assert train_ids & val_ids == set()
    assert train_ids & test_ids == set()
    assert val_ids & test_ids == set()
    assert len(train_ids) > len(val_ids) and len(train_ids) > len(test_ids)
    assert train_ids | val_ids | test_ids == {p["id"] for p in CATALOG}


def test_titles_are_nonempty_strings():
    pairs = generate_pairs(CATALOG, n_pairs=200, seed=4)
    for p in pairs:
        assert isinstance(p["text_a"], str) and p["text_a"].strip()
        assert isinstance(p["text_b"], str) and p["text_b"].strip()
