"""Summary report generator for the LLM Brand Visibility and Ranking Framework.

Produces a consolidated report with:
1. Overall brand ranking (all models combined)
2. Brand ranking per model (Claude vs GPT vs Gemini)
3. Brand visibility by prompt cluster (informational, commercial, navigational, comparison)
4. Model comparison: which model favors which brands
5. Top movers: brands with highest variance across models
6. Prompt cluster effectiveness: which cluster type triggers the most brand mentions
7. Detection method breakdown (exact vs domain vs fuzzy)

Output formats: Markdown report + CSV tables + console summary.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

from src.analyzer import bootstrap_ci, cliffs_delta, interpret_cliffs_delta
from src.config import StudyConfig


# ===========================================================================
# Report data builders
# ===========================================================================

def _brand_ranking_table(df: pd.DataFrame, group_cols: list[str] | None = None) -> pd.DataFrame:
    """Build a brand ranking table with all visibility metrics."""
    group = group_cols or []
    base_group = group + ["brand"]

    agg = (
        df.groupby(base_group)
        .agg(
            total_responses=("brand_found", "count"),
            times_mentioned=("brand_found", "sum"),
            mention_rate=("brand_found", "mean"),
            times_top3=("top3", "sum"),
            top3_rate=("top3", "mean"),
            avg_rank=("rank_position", lambda x: x[x < 999].mean() if (x < 999).any() else np.nan),
            median_rank=("rank_position", lambda x: x[x < 999].median() if (x < 999).any() else np.nan),
            avg_visibility=("visibility_score", "mean"),
            max_visibility=("visibility_score", "max"),
        )
        .reset_index()
    )

    # Calculate overall visibility rank
    agg["mention_rate_pct"] = (agg["mention_rate"] * 100).round(1)
    agg["top3_rate_pct"] = (agg["top3_rate"] * 100).round(1)
    agg["avg_visibility"] = agg["avg_visibility"].round(2)

    # Sort by mention rate descending
    agg = agg.sort_values(
        group + ["mention_rate"], ascending=[True] * len(group) + [False]
    )

    # Add rank within each group
    if group:
        agg["rank"] = agg.groupby(group).cumcount() + 1
    else:
        agg["rank"] = range(1, len(agg) + 1)

    return agg


def _cluster_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Summarize brand visibility per prompt cluster."""
    agg = (
        df.groupby(["cluster"])
        .agg(
            total_evaluations=("brand_found", "count"),
            total_mentions=("brand_found", "sum"),
            mention_rate=("brand_found", "mean"),
            top3_rate=("top3", "mean"),
            avg_visibility=("visibility_score", "mean"),
            unique_brands_mentioned=("brand", lambda x: x[df.loc[x.index, "brand_found"] == 1].nunique()),
        )
        .reset_index()
    )
    agg["mention_rate_pct"] = (agg["mention_rate"] * 100).round(1)
    agg["top3_rate_pct"] = (agg["top3_rate"] * 100).round(1)
    return agg.sort_values("mention_rate", ascending=False)


def _model_brand_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Create a model x brand matrix showing mention rates."""
    pivot = df.pivot_table(
        index="brand",
        columns="model",
        values="brand_found",
        aggfunc="mean",
    ).round(3)
    pivot.columns = [f"{col}_mention_rate" for col in pivot.columns]
    pivot["avg_across_models"] = pivot.mean(axis=1).round(3)
    pivot = pivot.sort_values("avg_across_models", ascending=False)
    return pivot.reset_index()


def _model_brand_rank_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Create a model x brand matrix showing average rank position (only when mentioned)."""
    mentioned = df[df["rank_position"] < 999].copy()
    if mentioned.empty:
        return pd.DataFrame()

    pivot = mentioned.pivot_table(
        index="brand",
        columns="model",
        values="rank_position",
        aggfunc="mean",
    ).round(1)
    pivot.columns = [f"{col}_avg_rank" for col in pivot.columns]
    pivot["avg_rank_overall"] = pivot.mean(axis=1).round(1)
    pivot = pivot.sort_values("avg_rank_overall", ascending=True)
    return pivot.reset_index()


def _cluster_brand_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Create a cluster x brand matrix showing mention rates."""
    pivot = df.pivot_table(
        index="brand",
        columns="cluster",
        values="brand_found",
        aggfunc="mean",
    ).round(3)
    pivot.columns = [f"{col}_mention_rate" for col in pivot.columns]
    pivot["avg_across_clusters"] = pivot.mean(axis=1).round(3)
    pivot = pivot.sort_values("avg_across_clusters", ascending=False)
    return pivot.reset_index()


def _model_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """Compare models on aggregate metrics."""
    agg = (
        df.groupby("model")
        .agg(
            total_evaluations=("brand_found", "count"),
            total_mentions=("brand_found", "sum"),
            mention_rate=("brand_found", "mean"),
            top3_rate=("top3", "mean"),
            avg_visibility=("visibility_score", "mean"),
            unique_brands=("brand", lambda x: x[df.loc[x.index, "brand_found"] == 1].nunique()),
        )
        .reset_index()
    )
    agg["mention_rate_pct"] = (agg["mention_rate"] * 100).round(1)
    return agg


def _brand_volatility(df: pd.DataFrame) -> pd.DataFrame:
    """Find brands with highest variance in mention rate across models."""
    model_rates = df.pivot_table(
        index="brand", columns="model", values="brand_found", aggfunc="mean"
    )
    volatility = pd.DataFrame({
        "brand": model_rates.index,
        "min_rate": model_rates.min(axis=1).round(3),
        "max_rate": model_rates.max(axis=1).round(3),
        "range": (model_rates.max(axis=1) - model_rates.min(axis=1)).round(3),
        "std": model_rates.std(axis=1).round(3),
        "mean_rate": model_rates.mean(axis=1).round(3),
    }).reset_index(drop=True)
    return volatility.sort_values("range", ascending=False)


def _detection_method_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Break down detections by match method (exact, domain, fuzzy)."""
    if "match_method" not in df.columns:
        return pd.DataFrame()

    found = df[df["brand_found"] == 1]
    if found.empty:
        return pd.DataFrame()

    breakdown = (
        found.groupby(["match_method"])
        .agg(
            count=("brand_found", "count"),
            unique_brands=("brand", "nunique"),
        )
        .reset_index()
    )
    breakdown["pct"] = (breakdown["count"] / breakdown["count"].sum() * 100).round(1)
    return breakdown.sort_values("count", ascending=False)


# ===========================================================================
# Markdown report generator
# ===========================================================================

def _df_to_markdown(df: pd.DataFrame, max_rows: int = 50) -> str:
    """Convert DataFrame to markdown table."""
    if df.empty:
        return "*No data available.*\n"

    df_show = df.head(max_rows)
    lines = []

    # Header
    headers = " | ".join(str(col) for col in df_show.columns)
    lines.append(f"| {headers} |")
    lines.append("|" + "|".join("---" for _ in df_show.columns) + "|")

    # Rows
    for _, row in df_show.iterrows():
        values = " | ".join(
            f"{v:.1%}" if isinstance(v, float) and 0 <= v <= 1 and "rate" in str(row.name if hasattr(row, 'name') else '')
            else f"{v:.2f}" if isinstance(v, float)
            else str(v)
            for v in row.values
        )
        lines.append(f"| {values} |")

    if len(df) > max_rows:
        lines.append(f"\n*... and {len(df) - max_rows} more rows (see CSV for full data).*\n")

    return "\n".join(lines)


def generate_report(
    metrics_df: pd.DataFrame,
    output_dir: str | Path | None = None,
) -> str:
    """
    Generate the full summary report.

    Args:
        metrics_df: Parsed metrics DataFrame from parser.py
        output_dir: Where to save report files

    Returns:
        Markdown report string
    """
    cfg = StudyConfig.load()
    output_dir = Path(output_dir) if output_dir else cfg.results_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    df = metrics_df.copy()
    n_responses = df["run_id"].nunique() if "run_id" in df.columns else 0
    n_prompts = df["prompt_id"].nunique() if "prompt_id" in df.columns else 0
    n_models = df["model"].nunique() if "model" in df.columns else 0
    n_brands = df["brand"].nunique() if "brand" in df.columns else 0
    models = sorted(df["model"].unique()) if "model" in df.columns else []

    # Build all report tables
    overall_ranking = _brand_ranking_table(df)
    per_model_ranking = _brand_ranking_table(df, group_cols=["model"])
    cluster_summary = _cluster_summary(df)
    model_brand_matrix = _model_brand_matrix(df)
    model_brand_ranks = _model_brand_rank_matrix(df)
    cluster_brand_matrix = _cluster_brand_matrix(df)
    model_comparison = _model_comparison(df)
    brand_volatility = _brand_volatility(df)
    detection_breakdown = _detection_method_breakdown(df)

    # Save all CSV tables
    overall_ranking.to_csv(output_dir / "report_overall_ranking.csv", index=False)
    per_model_ranking.to_csv(output_dir / "report_per_model_ranking.csv", index=False)
    cluster_summary.to_csv(output_dir / "report_cluster_summary.csv", index=False)
    model_brand_matrix.to_csv(output_dir / "report_model_brand_mention_matrix.csv", index=False)
    if not model_brand_ranks.empty:
        model_brand_ranks.to_csv(output_dir / "report_model_brand_rank_matrix.csv", index=False)
    cluster_brand_matrix.to_csv(output_dir / "report_cluster_brand_matrix.csv", index=False)
    model_comparison.to_csv(output_dir / "report_model_comparison.csv", index=False)
    brand_volatility.to_csv(output_dir / "report_brand_volatility.csv", index=False)
    if not detection_breakdown.empty:
        detection_breakdown.to_csv(output_dir / "report_detection_methods.csv", index=False)

    # ---- Build Markdown report ----
    report_lines = []
    r = report_lines.append

    r(f"# LLM Brand Visibility Report")
    r(f"")
    r(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    r(f"**Framework:** LLM Brand Visibility and Ranking Framework v{cfg.__class__.__module__}")
    r(f"")
    r(f"## Study Overview")
    r(f"")
    r(f"| Parameter | Value |")
    r(f"|-----------|-------|")
    r(f"| Models | {', '.join(models)} |")
    r(f"| Brands tracked | {n_brands} |")
    r(f"| Prompts | {n_prompts} |")
    r(f"| Total evaluations | {len(df):,} |")
    r(f"| Total brand mentions | {int(df['brand_found'].sum()):,} |")
    r(f"| Overall mention rate | {df['brand_found'].mean():.1%} |")
    r(f"")

    # --- Section 1: Model comparison ---
    r(f"## 1. Model Comparison")
    r(f"")
    r(f"How do the three models differ in brand recommendation behavior?")
    r(f"")
    r(f"| Model | Mention Rate | Top-3 Rate | Avg Visibility | Unique Brands |")
    r(f"|-------|-------------|-----------|---------------|--------------|")
    for _, row in model_comparison.iterrows():
        r(f"| {row['model']} | {row['mention_rate']:.1%} | {row['top3_rate']:.1%} | {row['avg_visibility']:.2f} | {int(row['unique_brands'])} |")
    r(f"")

    # --- Section 2: Overall brand ranking ---
    r(f"## 2. Overall Brand Ranking (All Models Combined)")
    r(f"")
    r(f"Brands ranked by mention rate across all models and prompt types.")
    r(f"")
    r(f"| Rank | Brand | Mention Rate | Top-3 Rate | Avg Rank | Avg Visibility | Times Mentioned |")
    r(f"|------|-------|-------------|-----------|----------|---------------|----------------|")
    for _, row in overall_ranking.head(30).iterrows():
        avg_rank = f"{row['avg_rank']:.1f}" if pd.notna(row['avg_rank']) else "N/A"
        r(f"| {int(row['rank'])} | {row['brand']} | {row['mention_rate']:.1%} | {row['top3_rate']:.1%} | {avg_rank} | {row['avg_visibility']:.2f} | {int(row['times_mentioned'])} |")
    if len(overall_ranking) > 30:
        r(f"")
        r(f"*Showing top 30 of {len(overall_ranking)} brands. Full data in `report_overall_ranking.csv`.*")
    r(f"")

    # --- Section 3: Brand ranking per model ---
    r(f"## 3. Brand Ranking per Model")
    r(f"")
    for model in models:
        model_data = per_model_ranking[per_model_ranking["model"] == model]
        r(f"### {model.upper()}")
        r(f"")
        r(f"| Rank | Brand | Mention Rate | Top-3 Rate | Avg Visibility |")
        r(f"|------|-------|-------------|-----------|---------------|")
        for _, row in model_data.head(15).iterrows():
            r(f"| {int(row['rank'])} | {row['brand']} | {row['mention_rate']:.1%} | {row['top3_rate']:.1%} | {row['avg_visibility']:.2f} |")
        r(f"")

    # --- Section 4: Prompt cluster analysis ---
    r(f"## 4. Visibility by Prompt Cluster")
    r(f"")
    r(f"Which type of query triggers the most brand mentions?")
    r(f"")
    r(f"| Cluster | Mention Rate | Top-3 Rate | Avg Visibility | Unique Brands Mentioned |")
    r(f"|---------|-------------|-----------|---------------|------------------------|")
    for _, row in cluster_summary.iterrows():
        r(f"| {row['cluster']} | {row['mention_rate']:.1%} | {row['top3_rate']:.1%} | {row['avg_visibility']:.2f} | {int(row['unique_brands_mentioned'])} |")
    r(f"")

    # --- Section 5: Model x Brand mention matrix (top 20) ---
    r(f"## 5. Model x Brand Mention Matrix (Top 20)")
    r(f"")
    r(f"Mention rate per brand per model — shows which model favors which brands.")
    r(f"")
    model_cols = [c for c in model_brand_matrix.columns if c.endswith("_mention_rate") and c != "avg_across_models"]
    header = "| Brand | " + " | ".join(c.replace("_mention_rate", "").upper() for c in model_cols) + " | Avg |"
    r(header)
    r("|" + "|".join("---" for _ in range(len(model_cols) + 2)) + "|")
    for _, row in model_brand_matrix.head(20).iterrows():
        vals = " | ".join(f"{row[c]:.1%}" for c in model_cols)
        r(f"| {row['brand']} | {vals} | {row['avg_across_models']:.1%} |")
    r(f"")

    # --- Section 6: Cluster x Brand matrix (top 20) ---
    r(f"## 6. Cluster x Brand Matrix (Top 20)")
    r(f"")
    r(f"How brand visibility differs by query type.")
    r(f"")
    cluster_cols = [c for c in cluster_brand_matrix.columns if c.endswith("_mention_rate") and c != "avg_across_clusters"]
    header = "| Brand | " + " | ".join(c.replace("_mention_rate", "").title() for c in cluster_cols) + " | Avg |"
    r(header)
    r("|" + "|".join("---" for _ in range(len(cluster_cols) + 2)) + "|")
    for _, row in cluster_brand_matrix.head(20).iterrows():
        vals = " | ".join(f"{row[c]:.1%}" for c in cluster_cols)
        r(f"| {row['brand']} | {vals} | {row['avg_across_clusters']:.1%} |")
    r(f"")

    # --- Section 7: Brand volatility ---
    r(f"## 7. Brand Volatility Across Models")
    r(f"")
    r(f"Brands with the highest variance in mention rate between models.")
    r(f"High volatility = model-dependent visibility (potential optimization target).")
    r(f"")
    r(f"| Brand | Min Rate | Max Rate | Range | Std Dev | Mean Rate |")
    r(f"|-------|---------|---------|-------|---------|-----------|")
    for _, row in brand_volatility.head(15).iterrows():
        r(f"| {row['brand']} | {row['min_rate']:.1%} | {row['max_rate']:.1%} | {row['range']:.1%} | {row['std']:.3f} | {row['mean_rate']:.1%} |")
    r(f"")

    # --- Section 8: Average rank positions ---
    if not model_brand_ranks.empty:
        r(f"## 8. Average Rank Position per Model (When Mentioned)")
        r(f"")
        r(f"Lower = better. Only includes responses where the brand appeared in a ranked list.")
        r(f"")
        rank_cols = [c for c in model_brand_ranks.columns if c.endswith("_avg_rank") and c != "avg_rank_overall"]
        header = "| Brand | " + " | ".join(c.replace("_avg_rank", "").upper() for c in rank_cols) + " | Avg |"
        r(header)
        r("|" + "|".join("---" for _ in range(len(rank_cols) + 2)) + "|")
        for _, row in model_brand_ranks.head(20).iterrows():
            vals = " | ".join(f"{row[c]:.1f}" if pd.notna(row[c]) else "N/A" for c in rank_cols)
            r(f"| {row['brand']} | {vals} | {row['avg_rank_overall']:.1f} |")
        r(f"")

    # --- Section 9: Detection method breakdown ---
    if not detection_breakdown.empty:
        r(f"## 9. Detection Method Breakdown")
        r(f"")
        r(f"How were brands detected in LLM responses?")
        r(f"")
        r(f"| Method | Count | % of Detections | Unique Brands |")
        r(f"|--------|-------|----------------|--------------|")
        for _, row in detection_breakdown.iterrows():
            r(f"| {row['match_method']} | {int(row['count']):,} | {row['pct']:.1f}% | {int(row['unique_brands'])} |")
        r(f"")

    # --- Section 10: Key findings ---
    r(f"## 10. Key Findings")
    r(f"")

    # Top brand
    if not overall_ranking.empty:
        top = overall_ranking.iloc[0]
        r(f"- **Most visible brand:** {top['brand']} ({top['mention_rate']:.1%} mention rate, {top['top3_rate']:.1%} top-3 rate)")

    # Most model-dependent brand
    if not brand_volatility.empty:
        vol = brand_volatility.iloc[0]
        r(f"- **Most model-dependent brand:** {vol['brand']} (mention rate range: {vol['min_rate']:.1%} to {vol['max_rate']:.1%})")

    # Best cluster for brand mentions
    if not cluster_summary.empty:
        best_cluster = cluster_summary.iloc[0]
        r(f"- **Best prompt type for brand mentions:** {best_cluster['cluster']} ({best_cluster['mention_rate']:.1%} mention rate)")

    # Model with most brand diversity
    if not model_comparison.empty:
        most_diverse = model_comparison.sort_values("unique_brands", ascending=False).iloc[0]
        r(f"- **Most brand-diverse model:** {most_diverse['model']} ({int(most_diverse['unique_brands'])} unique brands mentioned)")

    r(f"")
    r(f"---")
    r(f"")
    r(f"*Generated by [LLM Brand Visibility and Ranking Framework](https://github.com/AntonioBlago/llm-visibility-framework)*")
    r(f"*Author: Antonio Blago | [antonioblago.com](https://www.antonioblago.com) | [Visibly AI](https://www.visibly-ai.com)*")

    # Join and save
    report_text = "\n".join(report_lines)
    report_path = output_dir / "REPORT.md"
    report_path.write_text(report_text, encoding="utf-8")
    logger.info(f"Report saved to {report_path}")

    # Also print summary to console
    _print_console_summary(df, overall_ranking, model_comparison, cluster_summary, brand_volatility)

    return report_text


def _print_console_summary(
    df: pd.DataFrame,
    ranking: pd.DataFrame,
    model_comp: pd.DataFrame,
    cluster_sum: pd.DataFrame,
    volatility: pd.DataFrame,
) -> None:
    """Print a concise console summary."""
    print()
    print("=" * 70)
    print("LLM BRAND VISIBILITY REPORT")
    print("=" * 70)

    print(f"\nStudy: {df['model'].nunique()} models, {df['brand'].nunique()} brands, "
          f"{df['prompt_id'].nunique()} prompts")
    print(f"Total evaluations: {len(df):,}")
    print(f"Overall mention rate: {df['brand_found'].mean():.1%}")

    print(f"\n{'MODEL COMPARISON':^70}")
    print("-" * 70)
    for _, row in model_comp.iterrows():
        print(f"  {row['model']:>12}: mention={row['mention_rate']:.1%}  "
              f"top3={row['top3_rate']:.1%}  "
              f"brands={int(row['unique_brands'])}")

    print(f"\n{'TOP 10 BRANDS (ALL MODELS)':^70}")
    print("-" * 70)
    for _, row in ranking.head(10).iterrows():
        avg_rank = f"avg_rank={row['avg_rank']:.1f}" if pd.notna(row['avg_rank']) else "avg_rank=N/A"
        print(f"  #{int(row['rank']):>2} {row['brand']:>25}: "
              f"mention={row['mention_rate']:.1%}  "
              f"top3={row['top3_rate']:.1%}  "
              f"{avg_rank}")

    print(f"\n{'PROMPT CLUSTERS':^70}")
    print("-" * 70)
    for _, row in cluster_sum.iterrows():
        print(f"  {row['cluster']:>15}: mention={row['mention_rate']:.1%}  "
              f"brands={int(row['unique_brands_mentioned'])}")

    print(f"\n{'TOP 5 VOLATILE BRANDS':^70}")
    print("-" * 70)
    for _, row in volatility.head(5).iterrows():
        print(f"  {row['brand']:>25}: range={row['min_rate']:.1%}-{row['max_rate']:.1%}  "
              f"(spread={row['range']:.1%})")

    print("=" * 70)
    print()


# ===========================================================================
# CLI
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate Brand Visibility Summary Report")
    parser.add_argument("--input", type=str, default="data/parsed_metrics.csv",
                        help="Parsed metrics CSV from parser.py")
    parser.add_argument("--output-dir", type=str, default="results",
                        help="Output directory for report files")
    args = parser.parse_args()

    df = pd.read_csv(args.input, encoding="utf-8")
    generate_report(df, args.output_dir)


if __name__ == "__main__":
    main()
