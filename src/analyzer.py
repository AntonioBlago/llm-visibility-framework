"""Statistical analysis engine for the LLM Visibility Study.

Implements:
- Descriptive statistics per model/brand/cluster
- Significance tests (Fisher, Mann-Whitney, Wilcoxon, McNemar)
- Effect sizes (Odds Ratio, Cliff's Delta, Cohen's d)
- Bootstrap confidence intervals
- Benjamini-Hochberg FDR correction
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger
from scipy import stats
from statsmodels.stats.multitest import multipletests

from src.config import StudyConfig


# ===========================================================================
# Effect size functions
# ===========================================================================

def cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
    """
    Cliff's Delta: non-parametric effect size for ordinal data.

    Ranges from -1 to +1:
    - |d| < 0.147: negligible
    - |d| < 0.33: small
    - |d| < 0.474: medium
    - |d| >= 0.474: large
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n_x, n_y = len(x), len(y)
    if n_x == 0 or n_y == 0:
        return 0.0

    greater = sum(np.sum(xi > y) for xi in x)
    less = sum(np.sum(xi < y) for xi in x)
    return (greater - less) / (n_x * n_y)


def interpret_cliffs_delta(delta: float) -> str:
    """Interpret Cliff's Delta magnitude."""
    abs_d = abs(delta)
    if abs_d < 0.147:
        return "negligible"
    elif abs_d < 0.33:
        return "small"
    elif abs_d < 0.474:
        return "medium"
    return "large"


def cohens_d(x: np.ndarray, y: np.ndarray) -> float:
    """Cohen's d for two independent samples."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n_x, n_y = len(x), len(y)
    if n_x < 2 or n_y < 2:
        return 0.0
    pooled_std = np.sqrt(
        ((n_x - 1) * np.var(x, ddof=1) + (n_y - 1) * np.var(y, ddof=1))
        / (n_x + n_y - 2)
    )
    if pooled_std == 0:
        return 0.0
    return (np.mean(x) - np.mean(y)) / pooled_std


# ===========================================================================
# Bootstrap CI
# ===========================================================================

def bootstrap_ci(
    data: np.ndarray,
    func=np.mean,
    n_boot: int = 5000,
    ci: float = 95.0,
    seed: int = 42,
) -> tuple[float, float, float]:
    """
    Bootstrap confidence interval.

    Returns (point_estimate, lower_bound, upper_bound).
    """
    rng = np.random.default_rng(seed)
    data = np.asarray(data, dtype=float)
    data = data[~np.isnan(data)]

    if len(data) == 0:
        return np.nan, np.nan, np.nan

    boot_stats = [func(rng.choice(data, size=len(data), replace=True)) for _ in range(n_boot)]

    alpha = (100 - ci) / 2
    lower = np.percentile(boot_stats, alpha)
    upper = np.percentile(boot_stats, 100 - alpha)
    return float(func(data)), float(lower), float(upper)


def bootstrap_diff_ci(
    x: np.ndarray,
    y: np.ndarray,
    func=np.mean,
    n_boot: int = 5000,
    ci: float = 95.0,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Bootstrap CI for the difference between two groups."""
    rng = np.random.default_rng(seed)
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    diffs = []
    for _ in range(n_boot):
        x_sample = rng.choice(x, size=len(x), replace=True)
        y_sample = rng.choice(y, size=len(y), replace=True)
        diffs.append(func(x_sample) - func(y_sample))

    alpha = (100 - ci) / 2
    point = func(x) - func(y)
    return float(point), float(np.percentile(diffs, alpha)), float(np.percentile(diffs, 100 - alpha))


# ===========================================================================
# Statistical tests
# ===========================================================================

def test_mention_rate(a: pd.Series, b: pd.Series) -> dict:
    """Fisher's exact test for binary mention rates."""
    a_found = int(a.sum())
    a_not = len(a) - a_found
    b_found = int(b.sum())
    b_not = len(b) - b_found

    table = np.array([[a_found, a_not], [b_found, b_not]])

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        odds_ratio, p_value = stats.fisher_exact(table)

    return {
        "metric": "mention_rate",
        "test": "fisher_exact",
        "p_value": p_value,
        "effect_size": odds_ratio,
        "effect_type": "odds_ratio",
        "a_rate": a.mean(),
        "b_rate": b.mean(),
        "a_n": len(a),
        "b_n": len(b),
    }


def test_rank_position(a: pd.Series, b: pd.Series) -> dict:
    """Mann-Whitney U test for ordinal rank positions."""
    a_vals = a.dropna().values
    b_vals = b.dropna().values

    if len(a_vals) < 2 or len(b_vals) < 2:
        return {
            "metric": "rank_position",
            "test": "mann_whitney_u",
            "p_value": np.nan,
            "effect_size": 0.0,
            "effect_type": "cliffs_delta",
        }

    u_stat, p_value = stats.mannwhitneyu(a_vals, b_vals, alternative="two-sided")
    delta = cliffs_delta(a_vals, b_vals)

    return {
        "metric": "rank_position",
        "test": "mann_whitney_u",
        "p_value": p_value,
        "effect_size": delta,
        "effect_type": "cliffs_delta",
        "effect_interpretation": interpret_cliffs_delta(delta),
        "a_median": float(np.median(a_vals)),
        "b_median": float(np.median(b_vals)),
    }


def test_visibility_score(a: pd.Series, b: pd.Series) -> dict:
    """Mann-Whitney U test for visibility scores (ordinal/continuous)."""
    a_vals = a.dropna().values
    b_vals = b.dropna().values

    if len(a_vals) < 2 or len(b_vals) < 2:
        return {
            "metric": "visibility_score",
            "test": "mann_whitney_u",
            "p_value": np.nan,
            "effect_size": 0.0,
            "effect_type": "cliffs_delta",
        }

    u_stat, p_value = stats.mannwhitneyu(a_vals, b_vals, alternative="two-sided")
    delta = cliffs_delta(a_vals, b_vals)

    return {
        "metric": "visibility_score",
        "test": "mann_whitney_u",
        "p_value": p_value,
        "effect_size": delta,
        "effect_type": "cliffs_delta",
        "effect_interpretation": interpret_cliffs_delta(delta),
        "a_mean": float(np.mean(a_vals)),
        "b_mean": float(np.mean(b_vals)),
    }


def test_top3_rate(a: pd.Series, b: pd.Series) -> dict:
    """Fisher's exact test for top-3 inclusion rate."""
    a_in = int(a.sum())
    a_out = len(a) - a_in
    b_in = int(b.sum())
    b_out = len(b) - b_in

    table = np.array([[a_in, a_out], [b_in, b_out]])

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        odds_ratio, p_value = stats.fisher_exact(table)

    return {
        "metric": "top3_rate",
        "test": "fisher_exact",
        "p_value": p_value,
        "effect_size": odds_ratio,
        "effect_type": "odds_ratio",
        "a_rate": a.mean(),
        "b_rate": b.mean(),
    }


# ===========================================================================
# Full pairwise analysis
# ===========================================================================

def compare_two_conditions(
    df: pd.DataFrame,
    condition_col: str,
    cond_a: str,
    cond_b: str,
    group_by: str | None = None,
) -> pd.DataFrame:
    """
    Run all statistical tests comparing two conditions.

    Args:
        df: Parsed metrics DataFrame
        condition_col: Column name for the condition (e.g., 'model')
        cond_a: First condition value
        cond_b: Second condition value
        group_by: Optional grouping column (e.g., 'brand', 'cluster')

    Returns:
        DataFrame with test results per metric (and per group if specified).
    """
    results = []

    if group_by:
        groups = df[group_by].unique()
    else:
        groups = [None]

    for group in groups:
        if group is not None:
            sub = df[df[group_by] == group]
        else:
            sub = df

        a = sub[sub[condition_col] == cond_a]
        b = sub[sub[condition_col] == cond_b]

        if len(a) < 5 or len(b) < 5:
            continue

        # Run all 4 tests
        for test_fn in [test_mention_rate, test_rank_position, test_visibility_score, test_top3_rate]:
            if test_fn == test_mention_rate:
                result = test_fn(a["brand_found"], b["brand_found"])
            elif test_fn == test_rank_position:
                result = test_fn(a["rank_position"], b["rank_position"])
            elif test_fn == test_visibility_score:
                result = test_fn(a["visibility_score"], b["visibility_score"])
            elif test_fn == test_top3_rate:
                result = test_fn(a["top3"], b["top3"])

            result["condition_a"] = cond_a
            result["condition_b"] = cond_b
            if group is not None:
                result[group_by] = group
            results.append(result)

    results_df = pd.DataFrame(results)

    # Apply FDR correction
    if len(results_df) > 1 and results_df["p_value"].notna().sum() > 0:
        valid_mask = results_df["p_value"].notna()
        reject, corrected, _, _ = multipletests(
            results_df.loc[valid_mask, "p_value"],
            method="fdr_bh",
        )
        results_df.loc[valid_mask, "p_value_corrected"] = corrected
        results_df.loc[valid_mask, "significant"] = reject
    else:
        results_df["p_value_corrected"] = results_df["p_value"]
        results_df["significant"] = results_df["p_value"] < 0.05

    return results_df


# ===========================================================================
# Descriptive statistics
# ===========================================================================

def descriptive_stats(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """Compute descriptive statistics grouped by specified columns."""
    cfg = StudyConfig.load()

    agg = (
        df.groupby(group_cols)
        .agg(
            n_runs=("run_id", "nunique"),
            n_observations=("brand_found", "count"),
            mention_rate=("brand_found", "mean"),
            mention_rate_std=("brand_found", "std"),
            top3_rate=("top3", "mean"),
            avg_rank=("rank_position", "mean"),
            median_rank=("rank_position", "median"),
            avg_visibility=("visibility_score", "mean"),
            std_visibility=("visibility_score", "std"),
        )
        .reset_index()
    )

    # Add bootstrap CIs for mention rate
    ci_records = []
    for _, row in agg.iterrows():
        mask = True
        for col in group_cols:
            mask = mask & (df[col] == row[col])
        subset = df[mask]["brand_found"].values

        mean_val, lower, upper = bootstrap_ci(subset, func=np.mean, n_boot=cfg.bootstrap_n, seed=cfg.random_seed)
        ci_records.append({
            "mention_ci_lower": lower,
            "mention_ci_upper": upper,
        })

    ci_df = pd.DataFrame(ci_records)
    agg = pd.concat([agg.reset_index(drop=True), ci_df], axis=1)

    return agg


# ===========================================================================
# Full analysis pipeline
# ===========================================================================

def run_full_analysis(metrics_path: str | Path, output_dir: str | Path | None = None) -> dict:
    """
    Run the complete analysis pipeline.

    Returns dict with all result DataFrames.
    """
    cfg = StudyConfig.load()
    output_dir = Path(output_dir) if output_dir else cfg.results_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(metrics_path, encoding="utf-8")
    logger.info(f"Loaded {len(df)} metric records")

    # 1. Descriptive statistics
    desc_by_model = descriptive_stats(df, ["model"])
    desc_by_model_brand = descriptive_stats(df, ["model", "brand"])
    desc_by_model_cluster = descriptive_stats(df, ["model", "cluster"])
    desc_by_brand = descriptive_stats(df, ["brand"])

    desc_by_model.to_csv(output_dir / "descriptive_by_model.csv", index=False)
    desc_by_model_brand.to_csv(output_dir / "descriptive_by_model_brand.csv", index=False)
    desc_by_model_cluster.to_csv(output_dir / "descriptive_by_model_cluster.csv", index=False)
    desc_by_brand.to_csv(output_dir / "descriptive_by_brand.csv", index=False)

    logger.info("Descriptive statistics computed and saved")

    # 2. Pairwise model comparisons
    models = sorted(df["model"].unique())
    all_comparisons = []

    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            # Overall comparison
            comp = compare_two_conditions(df, "model", models[i], models[j])
            all_comparisons.append(comp)

            # Per-brand comparison
            comp_brand = compare_two_conditions(df, "model", models[i], models[j], group_by="brand")
            all_comparisons.append(comp_brand)

            # Per-cluster comparison
            comp_cluster = compare_two_conditions(df, "model", models[i], models[j], group_by="cluster")
            all_comparisons.append(comp_cluster)

    if all_comparisons:
        comparisons_df = pd.concat(all_comparisons, ignore_index=True)
        comparisons_df.to_csv(output_dir / "pairwise_comparisons.csv", index=False)
        logger.info(f"Pairwise comparisons: {len(comparisons_df)} tests")
    else:
        comparisons_df = pd.DataFrame()

    # 3. Bootstrap CIs for key metrics
    bootstrap_results = []
    for model in models:
        model_data = df[df["model"] == model]
        for metric_name, col in [("mention_rate", "brand_found"), ("visibility_score", "visibility_score"), ("top3_rate", "top3")]:
            vals = model_data[col].values
            mean_val, lower, upper = bootstrap_ci(vals, n_boot=cfg.bootstrap_n, seed=cfg.random_seed)
            bootstrap_results.append({
                "model": model,
                "metric": metric_name,
                "estimate": mean_val,
                "ci_lower": lower,
                "ci_upper": upper,
                "ci_width": upper - lower,
            })

    bootstrap_df = pd.DataFrame(bootstrap_results)
    bootstrap_df.to_csv(output_dir / "bootstrap_confidence_intervals.csv", index=False)

    logger.info("Analysis complete")

    return {
        "descriptive_by_model": desc_by_model,
        "descriptive_by_model_brand": desc_by_model_brand,
        "descriptive_by_model_cluster": desc_by_model_cluster,
        "descriptive_by_brand": desc_by_brand,
        "comparisons": comparisons_df,
        "bootstrap_cis": bootstrap_df,
    }


# ===========================================================================
# CLI
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="LLM Visibility Study — Statistical Analysis")
    parser.add_argument("--input", type=str, default="data/parsed_metrics.csv", help="Parsed metrics CSV")
    parser.add_argument("--output-dir", type=str, default="results", help="Output directory")
    args = parser.parse_args()

    run_full_analysis(args.input, args.output_dir)


if __name__ == "__main__":
    main()
