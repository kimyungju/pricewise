"""Tests for product-matching filtering inside compare_prices."""

from unittest.mock import MagicMock, patch

from pricewise.matching.matcher import MatcherUnavailable
from pricewise.tools.compare_prices import compare_prices

RESULTS = {
    "query": "AirPods Pro 2 price buy",
    "results": [
        {"url": "https://amazon.com/airpods-pro-2",
         "content": "Apple AirPods Pro (2nd Generation) - $249 at Amazon"},
        {"url": "https://bestbuy.com/airpods-max",
         "content": "Apple AirPods Max Silver - $549 at Best Buy"},
        {"url": "https://walmart.com/case",
         "content": "Silicone Case for AirPods Pro 2 - $12"},
    ],
}


def _tavily_mock():
    instance = MagicMock()
    instance.invoke.return_value = RESULTS
    return instance


def test_matcher_disabled_by_default_returns_all(monkeypatch):
    monkeypatch.delenv("MATCHER_ENABLED", raising=False)
    with patch("pricewise.tools.compare_prices.get_tavily", return_value=_tavily_mock()), \
         patch("pricewise.tools.compare_prices.get_matcher") as mock_get:
        result = compare_prices.invoke({"product_name": "AirPods Pro 2"})
    mock_get.assert_not_called()
    assert "airpods-max" in result and "walmart.com/case" in result


def test_matcher_enabled_filters_non_matching_listings(monkeypatch):
    monkeypatch.setenv("MATCHER_ENABLED", "true")
    monkeypatch.setenv("MATCH_THRESHOLD", "0.5")
    matcher = MagicMock()
    matcher.score.return_value = [0.94, 0.08, 0.21]  # real, different product, accessory
    with patch("pricewise.tools.compare_prices.get_tavily", return_value=_tavily_mock()), \
         patch("pricewise.tools.compare_prices.get_matcher", return_value=matcher):
        result = compare_prices.invoke({"product_name": "AirPods Pro 2"})
    assert "amazon.com/airpods-pro-2" in result
    assert "airpods-max" not in result
    assert "walmart.com/case" not in result


def test_matcher_enabled_annotates_match_score(monkeypatch):
    monkeypatch.setenv("MATCHER_ENABLED", "true")
    monkeypatch.setenv("MATCH_THRESHOLD", "0.5")
    matcher = MagicMock()
    matcher.score.return_value = [0.94, 0.08, 0.21]
    with patch("pricewise.tools.compare_prices.get_tavily", return_value=_tavily_mock()), \
         patch("pricewise.tools.compare_prices.get_matcher", return_value=matcher):
        result = compare_prices.invoke({"product_name": "AirPods Pro 2"})
    assert "match 0.94" in result


def test_all_below_threshold_reports_no_exact_match(monkeypatch):
    monkeypatch.setenv("MATCHER_ENABLED", "true")
    monkeypatch.setenv("MATCH_THRESHOLD", "0.5")
    matcher = MagicMock()
    matcher.score.return_value = [0.1, 0.2, 0.3]
    with patch("pricewise.tools.compare_prices.get_tavily", return_value=_tavily_mock()), \
         patch("pricewise.tools.compare_prices.get_matcher", return_value=matcher):
        result = compare_prices.invoke({"product_name": "AirPods Pro 2"})
    assert "no listings matched" in result.lower()
    assert "AirPods Pro 2" in result


def test_matcher_unavailable_falls_back_to_unfiltered(monkeypatch):
    monkeypatch.setenv("MATCHER_ENABLED", "true")
    matcher = MagicMock()
    matcher.score.side_effect = MatcherUnavailable("no weights")
    with patch("pricewise.tools.compare_prices.get_tavily", return_value=_tavily_mock()), \
         patch("pricewise.tools.compare_prices.get_matcher", return_value=matcher):
        result = compare_prices.invoke({"product_name": "AirPods Pro 2"})
    assert "amazon.com/airpods-pro-2" in result
    assert "airpods-max" in result
