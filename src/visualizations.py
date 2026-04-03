"""Visualization module for the LLM Visibility Study.

Generates publication-ready charts for:
- Power analysis heatmaps (runs x prompts)
- Model comparison bar charts
- Brand visibility rankings
- Bootstrap confidence interval plots
- Effect size forest plots
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from loguru import logger


# ---------------------------------------------------------------------------
# Style configuration
# ---------------------------------------------------------------------------

COLORS = {
    "claude": "#d97706",    # Anthropic orange
    "gpt": "#10b981",       # OpenAI green
    "gemini": "#3b82f6",    # Google blue
    "accent": "#f97316",    # Visibly AI orange
    "bg_dark": "#0f172a",
    "bg_card": "#1e293b",
    "text": "#e2e8f0",
    "grid": "#334155",
    "success": "#22c55e",
    "warning": "#eab308",
    "danger": "#ef4444",
}

MODEL_COLORS = {
    "claude": COLORS["claude"],
    "gpt": COLORS["gpt"],
    "gemini": COLORS["gemini"],
}


def setup_style():
    """Apply consistent dark theme for all plots."""
    plt.rcParams.update({
        "figure.facecolor": COLORS["bg_dark"],
        "axes.facecolor": COLORS["bg_card"],
        "axes.edgecolor": COLORS["grid"],
        "axes.labelcolor": COLORS["text"],
        "text.color": COLORS["text"],
        "xtick.color": COLORS["text"],
        "ytick.color": COLORS["text"],
        "grid.color": COLORS["grid"],
        "grid.alpha": 0.3,
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.titlesize": 14,
        "axes.labelsize": 12,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.facecolor": COLORS["bg_dark"],
    })


# ---------------------------------------------------------------------------
# Power analysis heatmap
# ---------------------------------------------------------------------------

def plot_power_heatmap(
    power_df: pd.DataFrame,
    metric: str = "mention_rate",
    scenario: str = "medium_15pp",
    output_path: Path | None = None,
) -> plt.Figure:
    """
    Create a heatmap showing statistical power across runs x prompts.

    Green = sufficient power (>= 80%), yellow = marginal, red = insufficient.
    """
    setup_style()

    subset = power_df[
        (power_df["metric"] == metric) & (power_df["scenario"] == scenario)
    ]

    if subset.empty:
        logger.warning(f"No data for metric={metric}, scenario={scenario}")
        return plt.figure()

    pivot = subset.pivot_table(
        index="n_runs", columns="n_prompts", values="power", aggfunc="first"
    )

    fig, ax = plt.subplots(figsize=(10, 6))

    # Custom colormap: red -> yellow -> green
    cmap = sns.diverging_palette(10, 130, s=80, l=55, n=256, as_cmap=True)

    sns.heatmap(
        pivot,
        annot=True,
        fmt=".0%",
        cmap=cmap,
        center=0.80,
        vmin=0.0,
        vmax=1.0,
        linewidths=2,
        linecolor=COLORS["bg_dark"],
        cbar_kws={"label": "Statistical Power", "shrink": 0.8},
        ax=ax,
    )

    # Add total API calls as secondary labels
    for i, n_runs in enumerate(pivot.index):
        for j, n_prompts in enumerate(pivot.columns):
            total_calls = n_runs * n_prompts * 3
            ax.text(
                j + 0.5, i + 0.75,
                f"({total_calls:,} calls)",
                ha="center", va="center",
                fontsize=7, color=COLORS["text"], alpha=0.6,
            )

    scenario_label = subset.iloc[0].get("scenario_label", scenario)
    ax.set_title(f"Statistical Power: {metric}\nScenario: {scenario_label}", pad=15)
    ax.set_xlabel("Number of Prompts (generic, no brand names)")
    ax.set_ylabel("Runs per Prompt")

    # Add 80% threshold line annotation
    ax.text(
        0.02, -0.08,
        "Green >= 80% power (recommended)  |  Yellow = marginal  |  Red = insufficient",
        transform=ax.transAxes, fontsize=9, color=COLORS["text"], alpha=0.7,
    )

    if output_path:
        fig.savefig(output_path)
        logger.info(f"Saved: {output_path}")

    return fig


# ---------------------------------------------------------------------------
# Model comparison bar chart
# ---------------------------------------------------------------------------

def plot_model_comparison(
    desc_df: pd.DataFrame,
    metric: str = "mention_rate",
    output_path: Path | None = None,
) -> plt.Figure:
    """Bar chart comparing models on a specific metric."""
    setup_style()

    fig, ax = plt.subplots(figsize=(10, 6))

    models = desc_df["model"].values
    values = desc_df[metric].values

    colors = [MODEL_COLORS.get(m, COLORS["accent"]) for m in models]

    bars = ax.bar(models, values, color=colors, width=0.6, edgecolor="none")

    # Add CI whiskers if available
    ci_lower_col = f"{metric.split('_')[0]}_ci_lower" if "mention" in metric else None
    ci_upper_col = f"{metric.split('_')[0]}_ci_upper" if "mention" in metric else None

    if ci_lower_col and ci_lower_col in desc_df.columns:
        ci_lower = desc_df[ci_lower_col].values
        ci_upper = desc_df[ci_upper_col].values
        yerr_lower = values - ci_lower
        yerr_upper = ci_upper - values
        ax.errorbar(
            models, values,
            yerr=[yerr_lower, yerr_upper],
            fmt="none", ecolor=COLORS["text"], elinewidth=1.5, capsize=5,
        )

    # Add value labels on bars
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
            f"{val:.1%}" if val <= 1 else f"{val:.1f}",
            ha="center", va="bottom", fontsize=12, fontweight="bold",
        )

    ax.set_title(f"Model Comparison: {metric.replace('_', ' ').title()}")
    ax.set_ylabel(metric.replace("_", " ").title())
    ax.set_ylim(0, min(1.15, max(values) * 1.3))
    ax.grid(axis="y", alpha=0.3)

    if output_path:
        fig.savefig(output_path)
        logger.info(f"Saved: {output_path}")

    return fig


# ---------------------------------------------------------------------------
# Brand visibility ranking
# ---------------------------------------------------------------------------

def plot_brand_ranking(
    desc_df: pd.DataFrame,
    metric: str = "mention_rate",
    output_path: Path | None = None,
) -> plt.Figure:
    """Horizontal bar chart ranking brands by a metric."""
    setup_style()

    sorted_df = desc_df.sort_values(metric, ascending=True)

    fig, ax = plt.subplots(figsize=(10, 8))

    colors = [COLORS["accent"] if v >= sorted_df[metric].median() else COLORS["grid"]
              for v in sorted_df[metric]]

    ax.barh(sorted_df["brand"], sorted_df[metric], color=colors, height=0.6)

    for idx, (_, row) in enumerate(sorted_df.iterrows()):
        val = row[metric]
        label = f"{val:.1%}" if val <= 1 else f"{val:.1f}"
        ax.text(val + 0.005, idx, label, va="center", fontsize=10)

    ax.set_title(f"Brand Ranking: {metric.replace('_', ' ').title()}\n(All Models Combined)")
    ax.set_xlabel(metric.replace("_", " ").title())
    ax.grid(axis="x", alpha=0.3)

    if output_path:
        fig.savefig(output_path)
        logger.info(f"Saved: {output_path}")

    return fig


# ---------------------------------------------------------------------------
# Bootstrap CI comparison
# ---------------------------------------------------------------------------

def plot_bootstrap_cis(
    bootstrap_df: pd.DataFrame,
    metric: str = "mention_rate",
    output_path: Path | None = None,
) -> plt.Figure:
    """Forest plot showing bootstrap confidence intervals per model."""
    setup_style()

    subset = bootstrap_df[bootstrap_df["metric"] == metric]
    if subset.empty:
        return plt.figure()

    fig, ax = plt.subplots(figsize=(10, 5))

    for i, (_, row) in enumerate(subset.iterrows()):
        model = row["model"]
        color = MODEL_COLORS.get(model, COLORS["accent"])

        ax.plot(
            [row["ci_lower"], row["ci_upper"]], [i, i],
            color=color, linewidth=3, solid_capstyle="round",
        )
        ax.scatter([row["estimate"]], [i], color=color, s=100, zorder=5)
        ax.text(
            row["ci_upper"] + 0.005, i,
            f'{row["estimate"]:.1%} [{row["ci_lower"]:.1%}, {row["ci_upper"]:.1%}]',
            va="center", fontsize=10,
        )

    ax.set_yticks(range(len(subset)))
    ax.set_yticklabels(subset["model"].values)
    ax.set_title(f"95% Bootstrap Confidence Intervals: {metric.replace('_', ' ').title()}")
    ax.set_xlabel(metric.replace("_", " ").title())
    ax.grid(axis="x", alpha=0.3)

    if output_path:
        fig.savefig(output_path)
        logger.info(f"Saved: {output_path}")

    return fig


# ---------------------------------------------------------------------------
# Effect size forest plot
# ---------------------------------------------------------------------------

def plot_effect_sizes(
    comparisons_df: pd.DataFrame,
    metric: str = "rank_position",
    output_path: Path | None = None,
) -> plt.Figure:
    """Forest plot of Cliff's Delta effect sizes for pairwise comparisons."""
    setup_style()

    subset = comparisons_df[comparisons_df["metric"] == metric].copy()
    if subset.empty:
        return plt.figure()

    subset["comparison"] = subset["condition_a"] + " vs " + subset["condition_b"]
    if "brand" in subset.columns:
        subset["label"] = subset["comparison"] + " (" + subset["brand"].fillna("overall") + ")"
    else:
        subset["label"] = subset["comparison"]

    # Limit to top 20 most interesting
    subset = subset.head(20)

    fig, ax = plt.subplots(figsize=(12, max(6, len(subset) * 0.4)))

    y_pos = range(len(subset))

    for i, (_, row) in enumerate(subset.iterrows()):
        effect = row["effect_size"]
        sig = row.get("significant", False)
        color = COLORS["accent"] if sig else COLORS["grid"]

        ax.barh(i, effect, color=color, height=0.6, alpha=0.8)

        label = f'{effect:.3f}'
        if "effect_interpretation" in row and pd.notna(row["effect_interpretation"]):
            label += f' ({row["effect_interpretation"]})'
        if sig:
            label += " *"

        ax.text(
            effect + 0.01 if effect >= 0 else effect - 0.01,
            i,
            label,
            va="center", ha="left" if effect >= 0 else "right",
            fontsize=9,
        )

    ax.axvline(x=0, color=COLORS["text"], linewidth=0.5, alpha=0.5)

    # Effect size thresholds
    for threshold, label in [(0.147, "small"), (0.33, "medium"), (0.474, "large")]:
        ax.axvline(x=threshold, color=COLORS["warning"], linewidth=0.5, linestyle="--", alpha=0.3)
        ax.axvline(x=-threshold, color=COLORS["warning"], linewidth=0.5, linestyle="--", alpha=0.3)

    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(subset["label"].values, fontsize=9)
    ax.set_title(f"Effect Sizes: {metric.replace('_', ' ').title()}\n(* = significant after FDR correction)")
    ax.set_xlabel("Cliff's Delta (negative = A better, positive = B better)")
    ax.grid(axis="x", alpha=0.3)

    if output_path:
        fig.savefig(output_path)
        logger.info(f"Saved: {output_path}")

    return fig


# ---------------------------------------------------------------------------
# Cluster-level heatmap
# ---------------------------------------------------------------------------

def plot_cluster_model_heatmap(
    desc_df: pd.DataFrame,
    metric: str = "mention_rate",
    output_path: Path | None = None,
) -> plt.Figure:
    """Heatmap showing metric values per model x cluster."""
    setup_style()

    pivot = desc_df.pivot_table(index="cluster", columns="model", values=metric, aggfunc="first")

    fig, ax = plt.subplots(figsize=(10, 6))

    sns.heatmap(
        pivot,
        annot=True,
        fmt=".1%",
        cmap="YlOrRd",
        linewidths=2,
        linecolor=COLORS["bg_dark"],
        cbar_kws={"label": metric.replace("_", " ").title()},
        ax=ax,
    )

    ax.set_title(f"{metric.replace('_', ' ').title()} by Model and Prompt Cluster")

    if output_path:
        fig.savefig(output_path)
        logger.info(f"Saved: {output_path}")

    return fig


# ---------------------------------------------------------------------------
# Generate all figures
# ---------------------------------------------------------------------------

def generate_all_figures(results_dir: str | Path = "results") -> None:
    """Generate all publication-ready figures from analysis results."""
    results_dir = Path(results_dir)
    figures_dir = results_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    # Power analysis
    power_path = results_dir / "power_analysis.csv"
    if power_path.exists():
        power_df = pd.read_csv(power_path)
        for scenario in ["small_5pp", "medium_15pp", "large_25pp"]:
            plot_power_heatmap(
                power_df, metric="mention_rate", scenario=scenario,
                output_path=figures_dir / f"power_heatmap_{scenario}.png",
            )
        for scenario in ["rank_small", "rank_medium", "rank_large"]:
            plot_power_heatmap(
                power_df, metric="rank_position", scenario=scenario,
                output_path=figures_dir / f"power_heatmap_{scenario}.png",
            )

    # Descriptive stats
    desc_model_path = results_dir / "descriptive_by_model.csv"
    if desc_model_path.exists():
        desc_model = pd.read_csv(desc_model_path)
        for metric in ["mention_rate", "top3_rate", "avg_visibility"]:
            plot_model_comparison(
                desc_model, metric=metric,
                output_path=figures_dir / f"model_comparison_{metric}.png",
            )

    desc_brand_path = results_dir / "descriptive_by_brand.csv"
    if desc_brand_path.exists():
        desc_brand = pd.read_csv(desc_brand_path)
        for metric in ["mention_rate", "avg_visibility"]:
            plot_brand_ranking(
                desc_brand, metric=metric,
                output_path=figures_dir / f"brand_ranking_{metric}.png",
            )

    # Bootstrap CIs
    bootstrap_path = results_dir / "bootstrap_confidence_intervals.csv"
    if bootstrap_path.exists():
        bootstrap_df = pd.read_csv(bootstrap_path)
        for metric in ["mention_rate", "visibility_score", "top3_rate"]:
            plot_bootstrap_cis(
                bootstrap_df, metric=metric,
                output_path=figures_dir / f"bootstrap_ci_{metric}.png",
            )

    # Pairwise comparisons
    comp_path = results_dir / "pairwise_comparisons.csv"
    if comp_path.exists():
        comp_df = pd.read_csv(comp_path)
        for metric in ["mention_rate", "rank_position", "visibility_score"]:
            plot_effect_sizes(
                comp_df, metric=metric,
                output_path=figures_dir / f"effect_sizes_{metric}.png",
            )

    # Cluster heatmap
    desc_cluster_path = results_dir / "descriptive_by_model_cluster.csv"
    if desc_cluster_path.exists():
        desc_cluster = pd.read_csv(desc_cluster_path)
        plot_cluster_model_heatmap(
            desc_cluster, metric="mention_rate",
            output_path=figures_dir / f"cluster_model_heatmap.png",
        )

    logger.info(f"All figures saved to {figures_dir}")


if __name__ == "__main__":
    generate_all_figures()
