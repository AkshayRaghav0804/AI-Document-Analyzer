import pandas as pd

from docanalyzer.charts import auto_charts


def test_mixed_dataframe_produces_charts():
    df = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=60),
        "sales": range(60),
        "cost": [x * 0.5 for x in range(60)],
        "region": ["N", "S", "E"] * 20,
    })
    titles = [t for t, _ in auto_charts(df)]
    assert any("Trend" in t for t in titles)
    assert "Distributions" in titles
    assert "Correlation matrix" in titles
    assert any("region" in t for t in titles)


def test_text_only_and_empty_numeric_do_not_crash():
    assert isinstance(auto_charts(pd.DataFrame({"a": ["x", "y"]})), list)
    assert auto_charts(pd.DataFrame()) == []
