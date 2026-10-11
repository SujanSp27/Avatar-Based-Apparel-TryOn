import pytest

from ml.errors import PipelineError
from ml.sizing.engine import recommend


def test_interval_selection_and_score_not_probability(chart_rows):
    result = recommend(
        {"chest": 94, "waist": 78, "hip": 98, "shoulderWidth": 41}, chart_rows, "t-shirt", "regular"
    )
    assert result["recommendedSize"] == "M"
    assert result["score"] == 0
    assert all(v == "Good" for v in result["explanation"].values())
    assert "not a probability" in result["scoreMeaning"]


def test_fit_preference_and_brand_change_selection(chart_rows):
    m = {"chest": 97, "waist": 81, "hip": 101, "shoulderWidth": 42}
    regular = recommend(m, chart_rows, "t-shirt", "regular")
    loose = recommend(m, chart_rows, "t-shirt", "loose")
    assert regular["recommendedSize"] == "M"
    assert loose["recommendedSize"] == "L"
    shifted = [
        {**r, **{k: v + 6 for k, v in r.items() if k.endswith(("Min", "Max"))}} for r in chart_rows
    ]
    assert recommend(m, shifted, "t-shirt", "regular")["recommendedSize"] == "S"


def test_trousers_ignore_chest_and_missing_charts_fail(chart_rows):
    assert (
        recommend({"waist": 79, "hip": 98}, chart_rows, "trouser", "regular")["recommendedSize"]
        == "M"
    )
    with pytest.raises(PipelineError):
        recommend({}, [], "shirt", "regular")


def test_extreme_sizes_flag_and_deterministic_ties(chart_rows):
    m = {"chest": 170, "waist": 150, "hip": 170, "shoulderWidth": 62}
    a = recommend(m, chart_rows, "dress", "regular")
    assert a == recommend(m, chart_rows, "dress", "regular")
    assert a["outOfRange"] and a["score"] > 1
