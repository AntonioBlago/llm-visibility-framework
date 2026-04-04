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
from plotly.subplots import make_subplots
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
    """Apply Visibly AI dark theme to a Plotly figure."""
    fig.update_layout(
        paper_bgcolor=COLORS["dark"],
        plot_bgcolor=COLORS["card_bg"],
        font=dict(color=COLORS["text"], family="Montserrat, sans-serif", size=13),
        title_font=dict(size=18, color=COLORS["white"]),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=COLORS["text"])),
        hoverlabel=dict(bgcolor=COLORS["navy"], font_size=13, font_color=COLORS["white"]),
        margin=dict(l=60, r=40, t=80, b=60),
    )
    fig.update_xaxes(gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"])
    fig.update_yaxes(gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"])
    return fig


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def _pct(val: float) -> float:
    """Convert decimal rate (0.054) to percentage (5.4) for chart display."""
    return round(val * 100, 2)


def chart_brand_ranking(df: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart: top brands by mention rate."""
    ranking = (
        df.groupby("brand")
        .agg(mention_rate=("brand_found", "mean"), top3_rate=("top3", "mean"),
             avg_vis=("visibility_score", "mean"))
        .reset_index()
    )
    # Filter to brands with at least one mention
    ranking = ranking[ranking["mention_rate"] > 0].sort_values("mention_rate", ascending=True).tail(25)

    if ranking.empty:
        return go.Figure().update_layout(title="No brands detected")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=ranking["brand"],
        x=ranking["mention_rate"].apply(_pct),
        orientation="h",
        marker_color=COLORS["orange"],
        text=[f"{_pct(v):.1f}%" for v in ranking["mention_rate"]],
        textposition="outside",
        textfont=dict(color=COLORS["text"], size=11),
        hovertemplate="<b>%{y}</b><br>Mention Rate: %{x:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        title="Brand Visibility Ranking (Mention Rate)",
        xaxis_title="Mention Rate (%)",
        xaxis=dict(range=[0, _pct(ranking["mention_rate"].max()) * 1.3], ticksuffix="%"),
        height=max(500, len(ranking) * 28),
    )
    return _apply_theme(fig)


def chart_model_comparison_bars(df: pd.DataFrame) -> go.Figure:
    """Grouped bar chart: model comparison on key metrics."""
    model_stats = (
        df.groupby("model")
        .agg(mention_rate=("brand_found", "mean"), top3_rate=("top3", "mean"),
             avg_vis=("visibility_score", "mean"))
        .reset_index()
    )

    colors_mention = [MODEL_COLORS.get(m, COLORS["orange"]) for m in model_stats["model"]]
    def _hex_to_rgba(hex_color, alpha=0.6):
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"
    colors_top3 = [_hex_to_rgba(c) for c in colors_mention]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=model_stats["model"],
        y=model_stats["mention_rate"].apply(_pct),
        name="Mention Rate",
        marker_color=colors_mention,
        text=[f"{_pct(v):.1f}%" for v in model_stats["mention_rate"]],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        x=model_stats["model"],
        y=model_stats["top3_rate"].apply(_pct),
        name="Top-3 Rate",
        marker_color=colors_top3,
        text=[f"{_pct(v):.1f}%" for v in model_stats["top3_rate"]],
        textposition="outside",
    ))

    max_val = _pct(model_stats["mention_rate"].max())
    fig.update_layout(
        title="Model Comparison: Mention Rate & Top-3 Rate",
        yaxis_title="Rate (%)",
        yaxis=dict(range=[0, max_val * 1.4], ticksuffix="%"),
        barmode="group",
        height=450,
    )
    return _apply_theme(fig)


def chart_model_brand_heatmap(df: pd.DataFrame) -> go.Figure:
    """Heatmap: mention rate per brand per model."""
    pivot = df.pivot_table(index="brand", columns="model", values="brand_found", aggfunc="mean")
    # Only show brands that were mentioned at least once
    pivot = pivot.loc[pivot.max(axis=1) > 0]
    pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).head(20).index]

    if pivot.empty:
        return go.Figure().update_layout(title="No brand mentions detected")

    # Convert to percentages for display
    pct_values = pivot.values * 100

    fig = go.Figure(data=go.Heatmap(
        z=pct_values,
        x=[m.upper() for m in pivot.columns],
        y=pivot.index.tolist(),
        colorscale=[[0, COLORS["dark"]], [0.3, COLORS["navy"]], [0.6, COLORS["blue"]], [1, COLORS["orange"]]],
        text=[[f"{v:.1f}%" for v in row] for row in pct_values],
        texttemplate="%{text}",
        textfont={"size": 12, "color": COLORS["white"]},
        hovertemplate="<b>%{y}</b> on %{x}<br>Mention Rate: %{z:.1f}%<extra></extra>",
        colorbar=dict(title="Rate %", ticksuffix="%"),
    ))
    fig.update_layout(
        title=f"Brand Mention Rate by Model (Top {len(pivot)} Brands)",
        height=max(400, len(pivot) * 35),
        xaxis=dict(side="bottom"),
    )
    return _apply_theme(fig)


def chart_cluster_comparison(df: pd.DataFrame) -> go.Figure:
    """Bar chart: mention rate by prompt cluster."""
    cluster_stats = (
        df.groupby("cluster")
        .agg(mention_rate=("brand_found", "mean"), top3_rate=("top3", "mean"),
             brands_found=("brand", lambda x: x[df.loc[x.index, "brand_found"] == 1].nunique()))
        .reset_index()
        .sort_values("mention_rate", ascending=False)
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=cluster_stats["cluster"],
        y=cluster_stats["mention_rate"].apply(_pct),
        marker_color=[CLUSTER_COLORS.get(c, COLORS["orange"]) for c in cluster_stats["cluster"]],
        text=[f"{_pct(v):.2f}% ({int(b)} brands)" for v, b in
              zip(cluster_stats["mention_rate"], cluster_stats["brands_found"])],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Mention Rate: %{y:.2f}%<extra></extra>",
    ))

    max_val = _pct(cluster_stats["mention_rate"].max())
    fig.update_layout(
        title="Brand Visibility by Prompt Cluster",
        yaxis_title="Mention Rate (%)",
        yaxis=dict(range=[0, max_val * 1.5], ticksuffix="%"),
        height=420,
    )
    return _apply_theme(fig)


def chart_cluster_brand_heatmap(df: pd.DataFrame) -> go.Figure:
    """Heatmap: mention rate per brand per cluster."""
    pivot = df.pivot_table(index="brand", columns="cluster", values="brand_found", aggfunc="mean")
    pivot = pivot.loc[pivot.max(axis=1) > 0]
    pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).head(20).index]

    if pivot.empty:
        return go.Figure().update_layout(title="No brand mentions detected")

    pct_values = pivot.values * 100

    fig = go.Figure(data=go.Heatmap(
        z=pct_values,
        x=[c.title() for c in pivot.columns],
        y=pivot.index.tolist(),
        colorscale=[[0, COLORS["dark"]], [0.3, COLORS["navy"]], [0.6, COLORS["blue_light"]], [1, COLORS["teal"]]],
        text=[[f"{v:.1f}%" for v in row] for row in pct_values],
        texttemplate="%{text}",
        textfont={"size": 12, "color": COLORS["white"]},
        hovertemplate="<b>%{y}</b> in %{x}<br>Mention Rate: %{z:.1f}%<extra></extra>",
        colorbar=dict(title="Rate %", ticksuffix="%"),
    ))
    fig.update_layout(
        title=f"Brand Visibility by Prompt Type (Top {len(pivot)} Brands)",
        height=max(400, len(pivot) * 35),
    )
    return _apply_theme(fig)


def chart_brand_volatility(df: pd.DataFrame) -> go.Figure:
    """Dumbbell chart: brand mention rate range across models."""
    model_rates = df.pivot_table(index="brand", columns="model", values="brand_found", aggfunc="mean")
    volatility = pd.DataFrame({
        "brand": model_rates.index,
        "min_rate": model_rates.min(axis=1),
        "max_rate": model_rates.max(axis=1),
        "range": model_rates.max(axis=1) - model_rates.min(axis=1),
    })
    # Only brands with at least some mentions and real variance
    volatility = volatility[volatility["max_rate"] > 0]
    volatility = volatility.sort_values("range", ascending=True).tail(15)

    if volatility.empty:
        return go.Figure().update_layout(title="No volatility data")

    fig = go.Figure()

    # Range lines
    for _, row in volatility.iterrows():
        fig.add_trace(go.Scatter(
            x=[_pct(row["min_rate"]), _pct(row["max_rate"])],
            y=[row["brand"], row["brand"]],
            mode="lines",
            line=dict(color=COLORS["text_muted"], width=3),
            showlegend=False,
            hoverinfo="skip",
        ))

    # Min dots
    fig.add_trace(go.Scatter(
        x=volatility["min_rate"].apply(_pct),
        y=volatility["brand"],
        mode="markers",
        marker=dict(color=COLORS["blue"], size=12, line=dict(width=1, color=COLORS["white"])),
        name="Lowest Model",
        hovertemplate="<b>%{y}</b><br>Min: %{x:.1f}%<extra></extra>",
    ))

    # Max dots
    fig.add_trace(go.Scatter(
        x=volatility["max_rate"].apply(_pct),
        y=volatility["brand"],
        mode="markers",
        marker=dict(color=COLORS["orange"], size=12, line=dict(width=1, color=COLORS["white"])),
        name="Highest Model",
        hovertemplate="<b>%{y}</b><br>Max: %{x:.1f}%<extra></extra>",
    ))

    max_val = _pct(volatility["max_rate"].max())
    fig.update_layout(
        title="Brand Volatility: Mention Rate Range Across Models",
        xaxis_title="Mention Rate (%)",
        xaxis=dict(range=[0, max_val * 1.2], ticksuffix="%"),
        height=max(400, len(volatility) * 35),
    )
    return _apply_theme(fig)


def chart_visibility_distribution(df: pd.DataFrame) -> go.Figure:
    """Box plot: visibility score distribution per model (only mentioned brands)."""
    # Only include rows where brand was actually mentioned — otherwise all zeros
    mentioned = df[df["brand_found"] == 1]

    if mentioned.empty:
        return go.Figure().update_layout(title="No visibility scores (no mentions detected)")

    fig = go.Figure()
    for model in sorted(mentioned["model"].unique()):
        model_data = mentioned[mentioned["model"] == model]
        fig.add_trace(go.Box(
            y=model_data["visibility_score"],
            name=model.upper(),
            marker_color=MODEL_COLORS.get(model, COLORS["orange"]),
            boxmean=True,
            boxpoints="outliers",
        ))
    fig.update_layout(
        title="Visibility Score Distribution by Model (When Mentioned)",
        yaxis_title="Visibility Score (0-10)",
        yaxis=dict(range=[0, 11]),
        height=420,
    )
    return _apply_theme(fig)


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

        <!-- Charts -->
        <div class="section">
            <h2>Model Comparison</h2>
            <p>How do Claude, GPT-4o, and Gemini differ in brand recommendation behavior?</p>
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
