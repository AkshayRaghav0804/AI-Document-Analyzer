"""Automatic Plotly charts for a DataFrame. Each function returns (title, figure) pairs."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PRIMARY = "#4f46e5"
TEMPLATE = "plotly_white"
MAX_NUMERIC = 8
MAX_CATEGORICAL = 4

Chart = tuple[str, go.Figure]


def _style(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(template=TEMPLATE, height=height, margin=dict(l=20, r=20, t=50, b=20))
    return fig


def overview_charts(df: pd.DataFrame) -> list[Chart]:
    charts: list[Chart] = []
    missing = df.isnull().sum()
    missing = missing[missing > 0].sort_values(ascending=False).head(30)
    if not missing.empty:
        fig = px.bar(x=missing.index, y=missing.values, labels={"x": "Column", "y": "Missing values"},
                     color_discrete_sequence=["#dc2626"])
        charts.append(("Missing values", _style(fig)))
    return charts


def numeric_charts(df: pd.DataFrame) -> list[Chart]:
    numeric = df.select_dtypes(include="number")
    if numeric.empty:
        return []
    cols = list(numeric.columns[:MAX_NUMERIC])
    charts: list[Chart] = []

    n_rows = (len(cols) + 1) // 2
    fig = make_subplots(rows=n_rows, cols=2, subplot_titles=cols)
    for i, col in enumerate(cols):
        fig.add_trace(go.Histogram(x=df[col], marker_color=PRIMARY, showlegend=False),
                      row=i // 2 + 1, col=i % 2 + 1)
    charts.append(("Distributions", _style(fig, 300 * n_rows)))

    if len(numeric.columns) > 1:
        corr = numeric[list(numeric.columns[:20])].corr()
        fig = px.imshow(corr, color_continuous_scale="RdBu_r", zmin=-1, zmax=1, aspect="auto",
                        text_auto=".2f" if len(corr) <= 10 else False)
        charts.append(("Correlation matrix", _style(fig, max(400, 30 * len(corr)))))

    fig = go.Figure([go.Box(y=df[c], name=c, marker_color=PRIMARY) for c in cols])
    charts.append(("Outliers (box plots)", _style(fig, 400)))
    return charts


def categorical_charts(df: pd.DataFrame) -> list[Chart]:
    charts: list[Chart] = []
    cats = df.select_dtypes(include=["object", "string", "category"]).columns
    for col in cats[:MAX_CATEGORICAL]:
        if df[col].nunique() > 50:
            continue
        counts = df[col].value_counts().head(20)
        fig = px.bar(x=counts.index.astype(str), y=counts.values, labels={"x": col, "y": "Count"},
                     color_discrete_sequence=[PRIMARY])
        charts.append((f"Top values: {col}", _style(fig)))
    return charts


def time_series_charts(df: pd.DataFrame) -> list[Chart]:
    dates = df.select_dtypes(include=["datetime64[ns]", "datetime64"]).columns
    numeric = df.select_dtypes(include="number").columns
    if len(dates) == 0 or len(numeric) == 0:
        return []
    date_col = dates[0]
    ordered = df.sort_values(date_col)
    fig = go.Figure([go.Scatter(x=ordered[date_col], y=ordered[c], mode="lines", name=c) for c in numeric[:5]])
    return [(f"Trend over {date_col}", _style(fig, 400))]


def auto_charts(df: pd.DataFrame) -> list[Chart]:
    return (
        overview_charts(df)
        + time_series_charts(df)
        + numeric_charts(df)
        + categorical_charts(df)
    )
