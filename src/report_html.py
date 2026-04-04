"""Interactive HTML report with Plotly charts — Visibly AI branded.

Generates a self-contained HTML file with:
- Dark theme matching Visibly AI CI
- Interactive Plotly charts (hover, zoom, filter)
- Brand ranking tables
- Model comparison radar charts
- Cluster heatmaps
- Brand volatility analysis
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots  # noqa: F811
from loguru import logger

from src.config import StudyConfig


# ---------------------------------------------------------------------------
# Visibly AI color scheme
# ---------------------------------------------------------------------------

COLORS = {
    "orange": "#f97316",
    "orange_light": "#fb923c",
    "orange_dark": "#ea580c",
    "blue": "#2f8ae5",
    "blue_light": "#39a3d1",
    "navy": "#043959",
    "dark": "#0c1115",
    "near_black": "#171716",
    "card_bg": "rgba(30,41,59,0.85)",
    "teal": "#1abc9c",
    "red": "#cf2e2e",
    "light_gray": "#f8f8f8",
    "white": "#ffffff",
    "text": "#e2e8f0",
    "text_muted": "#94a3b8",
    "grid": "#334155",
}

MODEL_COLORS = {
    "claude": "#f97316",   # Orange (Anthropic)
    "gpt": "#10b981",      # Green (OpenAI)
    "gemini": "#3b82f6",   # Blue (Google)
}

CLUSTER_COLORS = {
    "informational": "#3b82f6",
    "commercial": "#f97316",
    "navigational": "#8b5cf6",
    "comparison": "#10b981",
}

PLOTLY_TEMPLATE = {
    "layout": {
        "paper_bgcolor": COLORS["dark"],
        "plot_bgcolor": COLORS["card_bg"],
        "font": {"color": COLORS["text"], "family": "Montserrat, sans-serif", "size": 13},
        "title": {"font": {"size": 18, "color": COLORS["white"]}},
        "xaxis": {"gridcolor": COLORS["grid"], "zerolinecolor": COLORS["grid"]},
        "yaxis": {"gridcolor": COLORS["grid"], "zerolinecolor": COLORS["grid"]},
        "legend": {"bgcolor": "rgba(0,0,0,0)", "font": {"color": COLORS["text"]}},
        "hoverlabel": {"bgcolor": COLORS["navy"], "font_size": 13, "font_color": COLORS["white"]},
    }
}


def _apply_theme(fig: go.Figure) -> go.Figure:
    """Apply Visibly AI dark theme to a Plotly figure. Does NOT override margin."""
    fig.update_layout(
        paper_bgcolor=COLORS["dark"],
        plot_bgcolor=COLORS["card_bg"],
        font=dict(color=COLORS["text"], family="Montserrat, sans-serif", size=13),
        title_font=dict(size=18, color=COLORS["white"]),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=COLORS["text"]), orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor=COLORS["navy"], font_size=13, font_color=COLORS["white"]),
    )
    fig.update_xaxes(gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"])
    fig.update_yaxes(gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"])
    return fig


def _hex_to_rgba(hex_color: str, alpha: float = 0.6) -> str:
    """Convert hex color to rgba string."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def _pct(val: float) -> float:
    """Convert decimal rate (0.054) to percentage (5.4) for chart display."""
    return round(val * 100, 2)


def chart_brand_ranking(df: pd.DataFrame) -> go.Figure:
    """Vertical bar chart: Top 15 brands by mention rate, bars going up."""
    ranking = (
        df.groupby("brand")
        .agg(mention_rate=("brand_found", "mean"), top3_rate=("top3", "mean"),
             avg_vis=("visibility_score", "mean"))
        .reset_index()
    )
    ranking = ranking[ranking["mention_rate"] > 0].sort_values("mention_rate", ascending=False).head(15)

    if ranking.empty:
        return go.Figure().update_layout(title="No brands detected")

    # Color gradient: top brands get orange, lower get muted
    max_rate = ranking["mention_rate"].max()
    colors = [
        COLORS["orange"] if r >= max_rate * 0.5 else COLORS["blue"] if r >= max_rate * 0.2 else COLORS["grid"]
        for r in ranking["mention_rate"]
    ]

    brands = ranking["brand"].tolist()
    rates = [_pct(v) for v in ranking["mention_rate"]]
    top3s = [_pct(v) for v in ranking["top3_rate"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=brands,
        y=rates,
        orientation="v",
        marker_color=colors,
        text=[f"{v:.1f}%" for v in rates],
        textposition="outside",
        textfont=dict(color=COLORS["text"], size=12),
        hovertext=[
            f"<b>{b}</b><br>Mention Rate: {r:.1f}%<br>Top-3 Rate: {t:.1f}%"
            for b, r, t in zip(brands, rates, top3s)
        ],
        hoverinfo="text",
    ))

    fig.update_layout(
        title="Top 15 Brands by Mention Rate",
        yaxis_title="Mention Rate (%)",
        yaxis=dict(range=[0, max(rates) * 1.25], ticksuffix="%"),
        xaxis_tickangle=-40,
        margin=dict(l=70, r=40, t=80, b=140),
        height=500,
    )
    return _apply_theme(fig)


def chart_model_comparison_bars(df: pd.DataFrame) -> go.Figure:
    """Grouped bar chart: one trace per model so each appears in the legend."""
    model_stats = (
        df.groupby("model")
        .agg(mention_rate=("brand_found", "mean"), top3_rate=("top3", "mean"),
             avg_vis=("visibility_score", "mean"))
        .reset_index()
    )

    fig = go.Figure()
    metrics = ["Mention Rate", "Top-3 Rate"]

    for _, row in model_stats.iterrows():
        model = row["model"]
        color = MODEL_COLORS.get(model, COLORS["orange"])
        mr = _pct(row["mention_rate"])
        t3 = _pct(row["top3_rate"])

        fig.add_trace(go.Bar(
            x=metrics,
            y=[mr, t3],
            name=model.upper(),
            marker_color=color,
            text=[f"{mr:.1f}%", f"{t3:.1f}%"],
            textposition="outside",
            textfont=dict(size=12),
        ))

    max_val = _pct(model_stats["mention_rate"].max())
    fig.update_layout(
        title="Model Comparison: Mention Rate & Top-3 Rate",
        yaxis_title="Rate (%)",
        yaxis=dict(range=[0, max_val * 1.5], ticksuffix="%"),
        barmode="group",
        height=450,
    )
    return _apply_theme(fig)


def chart_model_brand_heatmap(df: pd.DataFrame) -> go.Figure:
    """One subplot per model, side by side, so bar lengths are clearly comparable."""
    models = sorted(df["model"].unique())
    n_models = len(models)

    pivot = df.pivot_table(index="brand", columns="model", values="brand_found", aggfunc="mean").fillna(0)
    # Filter + sort by average
    pivot = pivot.loc[pivot.mean(axis=1) > 0]
    pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=True).tail(20).index]
    brand_list = pivot.index.tolist()

    if not brand_list:
        return go.Figure().update_layout(title="No brand mentions detected")

    fig = make_subplots(
        rows=1, cols=n_models,
        shared_yaxes=True,
        subplot_titles=[m.upper() for m in models],
        horizontal_spacing=0.03,
    )

    max_val = _pct(pivot.max().max())

    for i, model in enumerate(models, 1):
        color = MODEL_COLORS.get(model, COLORS["orange"])
        rates = pivot[model].reindex(brand_list)

        hover_texts = []
        for brand in brand_list:
            r = rates.get(brand, 0)
            avg = pivot.loc[brand].mean()
            mn = pivot.loc[brand].min()
            mx = pivot.loc[brand].max()
            hover_texts.append(
                f"<b>{brand}</b> — {model.upper()}<br>"
                f"Rate: {r:.1%}<br>"
                f"Avg: {avg:.1%} | Min: {mn:.1%} | Max: {mx:.1%}"
            )

        fig.add_trace(go.Bar(
            y=brand_list,
            x=rates.apply(_pct).values,
            orientation="h",
            marker_color=color,
            name=model.upper(),
            text=[f"{_pct(v):.0f}%" for v in rates.values],
            textposition="outside",
            textfont=dict(size=10, color=COLORS["text"]),
            hovertext=hover_texts,
            hoverinfo="text",
            showlegend=(i == 1),  # legend only once
        ), row=1, col=i)

        fig.update_xaxes(
            range=[0, max_val * 1.4], ticksuffix="%",
            gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"],
            row=1, col=i,
        )

    fig.update_layout(
        title="Brand Mention Rate by Model (Top 20)",
        margin=dict(l=200, r=60, t=100, b=60),
        height=max(600, len(brand_list) * 32),
        showlegend=False,
    )
    # Apply theme colors
    fig.update_layout(
        paper_bgcolor=COLORS["dark"],
        plot_bgcolor=COLORS["card_bg"],
        font=dict(color=COLORS["text"], family="Montserrat, sans-serif", size=12),
        title_font=dict(size=18, color=COLORS["white"]),
    )
    fig.update_yaxes(gridcolor=COLORS["grid"])
    # Style subplot titles
    for ann in fig.layout.annotations:
        ann.font = dict(size=14, color=COLORS["white"], family="Montserrat, sans-serif")

    return fig


def chart_cluster_comparison(df: pd.DataFrame) -> go.Figure:
    """Vertical grouped bar chart: mention rate per cluster, one bar per model."""
    models = sorted(df["model"].unique())

    cluster_model = (
        df.groupby(["cluster", "model"])
        .agg(
            mention_rate=("brand_found", "mean"),
            brands_found=("brand", lambda x: x[df.loc[x.index, "brand_found"] == 1].nunique()),
        )
        .reset_index()
    )
    clusters = sorted(cluster_model["cluster"].unique())

    fig = go.Figure()
    for model in models:
        m_data = cluster_model[cluster_model["model"] == model].set_index("cluster").reindex(clusters)
        color = MODEL_COLORS.get(model, COLORS["orange"])

        hover_texts = []
        for cluster in clusters:
            r = m_data.loc[cluster, "mention_rate"] if cluster in m_data.index else 0
            b = int(m_data.loc[cluster, "brands_found"]) if cluster in m_data.index else 0
            hover_texts.append(
                f"<b>{cluster.title()}</b> — {model.upper()}<br>"
                f"Mention Rate: {r:.1%}<br>"
                f"Unique Brands: {b}"
            )

        fig.add_trace(go.Bar(
            x=[c.title() for c in clusters],
            y=m_data["mention_rate"].apply(_pct).values,
            name=model.upper(),
            marker_color=color,
            text=[f"{_pct(v):.1f}%" for v in m_data["mention_rate"].values],
            textposition="outside",
            textfont=dict(size=11),
            hovertext=hover_texts,
            hoverinfo="text",
        ))

    max_val = _pct(cluster_model["mention_rate"].max())
    fig.update_layout(
        title="Brand Visibility by Prompt Cluster & Model",
        yaxis_title="Mention Rate (%)",
        yaxis=dict(range=[0, max_val * 1.4], ticksuffix="%"),
        barmode="group",
        height=480,
    )
    return _apply_theme(fig)


def chart_cluster_brand_heatmap(df: pd.DataFrame) -> go.Figure:
    """Vertical grouped bars: top 15 brands, one bar per cluster."""
    clusters = sorted(df["cluster"].unique())

    brand_cluster = (
        df.groupby(["brand", "cluster"])
        .agg(mention_rate=("brand_found", "mean"))
        .reset_index()
    )

    pivot = df.pivot_table(index="brand", columns="cluster", values="brand_found", aggfunc="mean")
    brand_avg = pivot.mean(axis=1)
    brand_list = brand_avg[brand_avg > 0].sort_values(ascending=False).head(15).index.tolist()

    if not brand_list:
        return go.Figure().update_layout(title="No brand mentions detected")

    fig = go.Figure()
    for cluster in clusters:
        cl_data = brand_cluster[brand_cluster["cluster"] == cluster].set_index("brand").reindex(brand_list)
        color = CLUSTER_COLORS.get(cluster, COLORS["orange"])

        fig.add_trace(go.Bar(
            x=brand_list,
            y=cl_data["mention_rate"].apply(_pct).fillna(0).values,
            name=cluster.title(),
            marker_color=color,
            text=[f"{_pct(v):.0f}%" if v > 0.005 else "" for v in cl_data["mention_rate"].fillna(0).values],
            textposition="outside",
            textfont=dict(size=9),
            hovertemplate="<b>%{x}</b> — " + cluster.title() + "<br>Mention Rate: %{y:.1f}%<extra></extra>",
        ))

    max_val = _pct(brand_cluster[brand_cluster["brand"].isin(brand_list)]["mention_rate"].max())
    fig.update_layout(
        title=f"Brand Visibility by Prompt Type (Top {len(brand_list)})",
        yaxis_title="Mention Rate (%)",
        yaxis=dict(range=[0, max_val * 1.3], ticksuffix="%"),
        xaxis_tickangle=-40,
        barmode="group",
        margin=dict(l=60, r=40, t=100, b=140),
        height=520,
    )
    return _apply_theme(fig)


def chart_brand_volatility(df: pd.DataFrame) -> go.Figure:
    """Lollipop chart: 3 horizontal lines per brand (one per model) from 0 to rate."""
    models = sorted(df["model"].unique())
    model_rates = df.pivot_table(index="brand", columns="model", values="brand_found", aggfunc="mean").fillna(0)

    # Filter + sort by spread
    spread = model_rates.max(axis=1) - model_rates.min(axis=1)
    has_mentions = model_rates.max(axis=1) > 0
    brand_list = spread[has_mentions].sort_values(ascending=True).tail(20).index.tolist()

    if not brand_list:
        return go.Figure().update_layout(title="No volatility data")

    n_models = len(models)
    # Vertical spacing: each brand gets a slot, models offset within that slot
    offsets = {models[i]: (i - (n_models - 1) / 2) * 0.28 for i in range(n_models)}

    fig = go.Figure()

    for model in models:
        color = MODEL_COLORS.get(model, COLORS["orange"])
        rates = model_rates.reindex(brand_list)[model]
        offset = offsets[model]

        y_vals = [i + offset for i in range(len(brand_list))]
        x_vals = [_pct(r) for r in rates.values]

        # Lines from 0 to rate
        for j, (x, y) in enumerate(zip(x_vals, y_vals)):
            fig.add_trace(go.Scatter(
                x=[0, x], y=[y, y],
                mode="lines",
                line=dict(color=color, width=3),
                showlegend=False,
                hoverinfo="skip",
            ))

        # Dots at the end
        hover_texts = []
        for brand in brand_list:
            r = rates.get(brand, 0)
            avg = model_rates.loc[brand].mean()
            mn = model_rates.loc[brand].min()
            mx = model_rates.loc[brand].max()
            hover_texts.append(
                f"<b>{brand}</b> — {model.upper()}<br>"
                f"Rate: {r:.1%}<br>"
                f"Avg: {avg:.1%} | Min: {mn:.1%} | Max: {mx:.1%}"
            )

        fig.add_trace(go.Scatter(
            x=x_vals,
            y=y_vals,
            mode="markers+text",
            marker=dict(color=color, size=10, line=dict(width=1, color=COLORS["white"])),
            text=[f"{v:.0f}%" for v in x_vals],
            textposition="middle right",
            textfont=dict(size=9, color=color),
            name=model.upper(),
            hovertext=hover_texts,
            hoverinfo="text",
        ))

    max_val = _pct(model_rates.reindex(brand_list).max().max())
    fig.update_layout(
        title="Brand Volatility: Mention Rate per Model",
        xaxis_title="Mention Rate (%)",
        xaxis=dict(range=[0, max_val * 1.25], ticksuffix="%"),
        yaxis=dict(
            tickvals=list(range(len(brand_list))),
            ticktext=brand_list,
        ),
        margin=dict(l=200, r=100, t=100, b=80),
        height=max(600, len(brand_list) * 50),
    )
    return _apply_theme(fig)


def chart_visibility_distribution(df: pd.DataFrame) -> go.Figure:
    """Grouped bar chart: avg visibility score per brand, split by model."""
    mentioned = df[df["brand_found"] == 1].copy()

    if mentioned.empty:
        return go.Figure().update_layout(title="No visibility scores (no mentions detected)")

    models = sorted(mentioned["model"].unique())

    # Avg visibility per brand x model
    brand_vis = mentioned.groupby(["brand", "model"])["visibility_score"].mean().reset_index()
    # Top 20 brands by overall avg
    top_brands = (
        mentioned.groupby("brand")["visibility_score"].mean()
        .sort_values(ascending=False).head(20).index.tolist()
    )
    brand_vis = brand_vis[brand_vis["brand"].isin(top_brands)]

    fig = go.Figure()
    for model in models:
        color = MODEL_COLORS.get(model, COLORS["orange"])
        m_data = brand_vis[brand_vis["model"] == model].set_index("brand").reindex(top_brands)

        fig.add_trace(go.Bar(
            x=top_brands,
            y=m_data["visibility_score"].fillna(0).values,
            name=model.upper(),
            marker_color=color,
            text=[f"{v:.1f}" if v > 0 else "" for v in m_data["visibility_score"].fillna(0).values],
            textposition="outside",
            textfont=dict(size=9),
            hovertemplate="<b>%{x}</b> — " + model.upper() + "<br>Avg Visibility: %{y:.1f}<extra></extra>",
        ))

    fig.update_layout(
        title="Avg Visibility Score per Brand & Model (When Mentioned)",
        yaxis_title="Visibility Score (0-10)",
        yaxis=dict(range=[0, 11], dtick=2),
        xaxis_tickangle=-45,
        barmode="group",
        margin=dict(l=60, r=40, t=100, b=150),
        height=520,
    )
    return _apply_theme(fig)


# ---------------------------------------------------------------------------
# HTML table builders
# ---------------------------------------------------------------------------

def _build_ranking_table(df: pd.DataFrame, title: str, model_filter: str | None = None) -> str:
    """Build an HTML ranking table for brands."""
    sub = df if model_filter is None else df[df["model"] == model_filter]
    ranking = (
        sub.groupby("brand")
        .agg(mention_rate=("brand_found", "mean"), top3_rate=("top3", "mean"),
             avg_rank=("rank_position", lambda x: x[x < 999].mean() if (x < 999).any() else None),
             avg_vis=("visibility_score", "mean"),
             times=("brand_found", "sum"))
        .reset_index()
        .sort_values("mention_rate", ascending=False)
    )
    ranking = ranking[ranking["mention_rate"] > 0].head(20)

    if ranking.empty:
        return f'<p class="text-muted">No brands detected.</p>'

    rows = ""
    for i, (_, r) in enumerate(ranking.iterrows(), 1):
        avg_r = f"{r['avg_rank']:.1f}" if pd.notna(r['avg_rank']) else "—"
        rows += f"""<tr>
            <td>#{i}</td><td>{r['brand']}</td>
            <td>{r['mention_rate']:.1%}</td><td>{r['top3_rate']:.1%}</td>
            <td>{avg_r}</td><td>{r['avg_vis']:.1f}</td><td>{int(r['times'])}</td>
        </tr>"""

    color = MODEL_COLORS.get(model_filter, COLORS["orange"]) if model_filter else COLORS["orange"]

    return f"""
    <div class="section"><h2 style="border-left-color:{color}">{title}</h2></div>
    <div class="table-wrapper">
    <table class="data-table">
        <thead><tr>
            <th>#</th><th>Brand</th><th>Mention Rate</th><th>Top-3 Rate</th>
            <th>Avg Rank</th><th>Avg Visibility</th><th>Mentions</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table></div>"""


def _build_volatility_table(df: pd.DataFrame) -> str:
    """Build an HTML table showing per-model mention rates + spread."""
    models = sorted(df["model"].unique())
    model_rates = df.pivot_table(index="brand", columns="model", values="brand_found", aggfunc="mean")

    volatility = pd.DataFrame({
        "brand": model_rates.index,
        "mean": model_rates.mean(axis=1),
        "min": model_rates.min(axis=1),
        "max": model_rates.max(axis=1),
        "spread": model_rates.max(axis=1) - model_rates.min(axis=1),
    })
    for m in models:
        volatility[m] = model_rates[m].values

    volatility = volatility[volatility["max"] > 0].sort_values("spread", ascending=False).head(25)

    if volatility.empty:
        return '<p class="text-muted">No data.</p>'

    # Header
    model_headers = "".join(f"<th>{m.upper()}</th>" for m in models)
    header = f"<tr><th>#</th><th>Brand</th>{model_headers}<th>Min</th><th>Max</th><th>Spread</th></tr>"

    # Rows
    rows = ""
    for i, (_, r) in enumerate(volatility.iterrows(), 1):
        model_cells = ""
        for m in models:
            val = r[m]
            # Color intensity based on value
            if val >= 0.15:
                bg = _hex_to_rgba(COLORS["orange"], 0.3)
            elif val >= 0.05:
                bg = _hex_to_rgba(COLORS["blue"], 0.2)
            elif val > 0:
                bg = _hex_to_rgba(COLORS["teal"], 0.15)
            else:
                bg = "transparent"
            model_cells += f'<td style="background:{bg}">{val:.1%}</td>'

        rows += f"""<tr>
            <td>#{i}</td><td>{r['brand']}</td>
            {model_cells}
            <td>{r['min']:.1%}</td><td>{r['max']:.1%}</td>
            <td style="font-weight:600;color:{COLORS['orange']}">{r['spread']:.1%}</td>
        </tr>"""

    return f"""
    <div class="section"><h2>Brand Visibility per Model + Spread</h2>
    <p>Mention rate per model. High spread = model-dependent visibility (GEO optimization target).</p></div>
    <div class="table-wrapper">
    <table class="data-table">
        <thead>{header}</thead>
        <tbody>{rows}</tbody>
    </table></div>"""


# ---------------------------------------------------------------------------
# HTML page builder
# ---------------------------------------------------------------------------

def generate_html_report(
    metrics_df: pd.DataFrame,
    output_path: str | Path | None = None,
) -> str:
    """Generate a self-contained interactive HTML report."""
    cfg = StudyConfig.load()
    output_path = Path(output_path) if output_path else cfg.results_dir / "report.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = metrics_df.copy()
    models = sorted(df["model"].unique())
    n_brands = df["brand"].nunique()
    n_prompts = df["prompt_id"].nunique()
    overall_mention = df["brand_found"].mean()

    # Build all charts
    charts = [
        ("overview", chart_model_comparison_bars(df)),
        ("brand_ranking", chart_brand_ranking(df)),
        ("model_heatmap", chart_model_brand_heatmap(df)),
        ("cluster_bars", chart_cluster_comparison(df)),
        ("cluster_heatmap", chart_cluster_brand_heatmap(df)),
        ("volatility", chart_brand_volatility(df)),
        ("distribution", chart_visibility_distribution(df)),
    ]

    # Convert charts to HTML divs
    chart_divs = ""
    for chart_id, fig in charts:
        chart_html = fig.to_html(full_html=False, include_plotlyjs=False, div_id=chart_id)
        chart_divs += f'<div class="chart-container">{chart_html}</div>\n'

    # Build HTML tables
    table_overall = _build_ranking_table(df, "Top Brands — All Models Combined")
    table_per_model = ""
    for model in models:
        color = MODEL_COLORS.get(model, COLORS["orange"])
        table_per_model += _build_ranking_table(df, f"Top Brands — {model.upper()}", model_filter=model)
    table_volatility = _build_volatility_table(df)

    # KPI cards
    model_stats = df.groupby("model").agg(
        mention_rate=("brand_found", "mean"),
        top3_rate=("top3", "mean"),
    ).reset_index()

    kpi_cards = ""
    for _, row in model_stats.iterrows():
        color = MODEL_COLORS.get(row["model"], COLORS["orange"])
        kpi_cards += f"""
        <div class="kpi-card" style="border-left-color: {color}">
            <div class="kpi-label">{row['model'].upper()}</div>
            <div class="kpi-value">{row['mention_rate']:.1%}</div>
            <div class="kpi-sub">Top-3: {row['top3_rate']:.1%}</div>
        </div>"""

    # Full HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM Brand Visibility Report — Visibly AI</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --orange: {COLORS['orange']};
            --dark: {COLORS['dark']};
            --card-bg: {COLORS['card_bg']};
            --navy: {COLORS['navy']};
            --teal: {COLORS['teal']};
            --text: {COLORS['text']};
            --text-muted: {COLORS['text_muted']};
            --grid: {COLORS['grid']};
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', sans-serif;
            background: var(--dark);
            color: var(--text);
            line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}

        /* Header */
        .header {{
            background: linear-gradient(135deg, var(--dark) 0%, var(--navy) 100%);
            padding: 3rem 2rem;
            border-bottom: 3px solid var(--orange);
            margin-bottom: 2rem;
        }}
        .header h1 {{
            font-family: 'Montserrat', sans-serif;
            font-size: 2rem;
            font-weight: 800;
            color: #fff;
            margin-bottom: 0.5rem;
        }}
        .header .subtitle {{
            color: var(--orange);
            font-family: 'Montserrat', sans-serif;
            font-weight: 600;
            font-size: 1.1rem;
        }}
        .header .meta {{
            color: var(--text-muted);
            margin-top: 1rem;
            font-size: 0.9rem;
        }}

        /* KPI Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        .kpi-card {{
            background: var(--card-bg);
            border-radius: 1rem;
            padding: 1.5rem;
            border-left: 0.25rem solid var(--orange);
            backdrop-filter: blur(10px);
        }}
        .kpi-label {{
            font-family: 'Montserrat', sans-serif;
            font-weight: 600;
            font-size: 0.85rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .kpi-value {{
            font-family: 'Montserrat', sans-serif;
            font-size: 2rem;
            font-weight: 800;
            color: #fff;
            margin: 0.25rem 0;
        }}
        .kpi-sub {{
            color: var(--text-muted);
            font-size: 0.9rem;
        }}

        /* Section */
        .section {{
            margin-bottom: 2.5rem;
        }}
        .section h2 {{
            font-family: 'Montserrat', sans-serif;
            font-size: 1.4rem;
            font-weight: 700;
            color: #fff;
            margin-bottom: 1rem;
            padding-left: 1rem;
            border-left: 4px solid var(--orange);
        }}
        .section p {{
            color: var(--text-muted);
            margin-bottom: 1rem;
            font-size: 0.95rem;
        }}

        /* Chart container */
        .chart-container {{
            background: var(--card-bg);
            border-radius: 1rem;
            padding: 1.5rem;
            margin-bottom: 2rem;
            backdrop-filter: blur(10px);
            border: 1px solid var(--grid);
        }}

        /* Overview stats */
        .overview-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .stat-item {{
            text-align: center;
            padding: 1rem;
            background: var(--card-bg);
            border-radius: 0.75rem;
        }}
        .stat-value {{
            font-family: 'Montserrat', sans-serif;
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--orange);
        }}
        .stat-label {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 0.25rem;
        }}

        /* Data Tables */
        .table-wrapper {{
            overflow-x: auto;
            margin-bottom: 2rem;
        }}
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}
        .data-table thead th {{
            background: var(--orange);
            color: #fff;
            font-family: 'Montserrat', sans-serif;
            font-weight: 600;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            padding: 0.75rem 1rem;
            text-align: left;
            white-space: nowrap;
        }}
        .data-table tbody td {{
            padding: 0.6rem 1rem;
            border-bottom: 1px solid var(--grid);
            white-space: nowrap;
        }}
        .data-table tbody tr:hover {{
            background: rgba(249, 115, 22, 0.06);
        }}
        .data-table tbody tr:nth-child(odd) {{
            background: rgba(30, 41, 59, 0.4);
        }}

        /* Footer */
        .footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
            font-size: 0.85rem;
            border-top: 1px solid var(--grid);
            margin-top: 3rem;
        }}
        .footer a {{ color: var(--orange); text-decoration: none; }}
        .footer a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <h1>LLM Brand Visibility Report</h1>
            <div class="subtitle">Supplement Market Germany — {n_brands} Brands Tracked</div>
            <div class="meta">
                Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} |
                Models: {', '.join(m.upper() for m in models)} |
                {n_prompts} Generic Prompts |
                {len(df):,} Total Evaluations
            </div>
        </div>
    </div>

    <div class="container">
        <!-- KPI Cards -->
        <div class="overview-stats">
            <div class="stat-item">
                <div class="stat-value">{n_brands}</div>
                <div class="stat-label">Brands Tracked</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{n_prompts}</div>
                <div class="stat-label">Generic Prompts</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{len(models)}</div>
                <div class="stat-label">LLM Models</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{overall_mention:.1%}</div>
                <div class="stat-label">Overall Mention Rate</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{len(df):,}</div>
                <div class="stat-label">Total Evaluations</div>
            </div>
        </div>

        <!-- Model KPIs -->
        <div class="section">
            <h2>Model Performance</h2>
            <p>Mention rate and top-3 inclusion rate per LLM provider.</p>
            <div class="kpi-grid">{kpi_cards}</div>
        </div>

        <!-- 1. Overall Ranking Table (first!) -->
        {table_overall}

        <!-- 2. Volatility / Spread Table -->
        {table_volatility}

        <!-- 3. Per-Model Ranking Tables -->
        {table_per_model}

        <!-- 4. Charts -->
        <div class="section">
            <h2>Charts</h2>
            <p>Interactive visualizations of brand visibility across models and prompt types.</p>
        </div>
        {chart_divs}

        <!-- Footer -->
        <div class="footer">
            Generated by <a href="https://github.com/AntonioBlago/llm-visibility-framework">LLM Brand Visibility Framework</a><br>
            <a href="https://www.antonioblago.com">Antonio Blago</a> | <a href="https://www.visibly-ai.com">Visibly AI</a>
        </div>
    </div>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    logger.info(f"HTML report saved to {output_path}")
    return str(output_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate interactive HTML report")
    parser.add_argument("--input", type=str, default="data/parsed_metrics.csv")
    parser.add_argument("--output", type=str, default="results/report.html")
    args = parser.parse_args()

    df = pd.read_csv(args.input, encoding="utf-8")
    generate_html_report(df, args.output)


if __name__ == "__main__":
    main()
