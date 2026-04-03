"""Similarity analysis between prompt runs.

Measures how consistent LLM outputs are across repeated runs of the same prompt.
This is critical for understanding output stability and determining the minimum
number of runs needed.

Metrics:
- **Jaccard Similarity**: Overlap of mentioned brand sets between runs
- **Rank Correlation (Kendall's Tau)**: How similar the ranking order is between runs
- **Rank-Biased Overlap (RBO)**: Top-weighted rank similarity (top positions matter more)
- **Intra-Class Correlation (ICC)**: Agreement across all runs for a prompt
- **Mention Consistency**: How often each brand appears across N runs (stability %)
- **Fleiss' Kappa**: Inter-rater agreement treating each run as a "rater"
"""

from __future__ import annotations

import argparse
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger
from scipy import stats


# ===========================================================================
# Pairwise similarity metrics
# ===========================================================================

def jaccard_similarity(set_a: set, set_b: set) -> float:
    """
    Jaccard index: |A intersect B| / |A union B|.

    Measures overlap of mentioned brand sets between two runs.
    1.0 = identical brand sets, 0.0 = no overlap.
    """
    if not set_a and not set_b:
        return 1.0  # Both empty = identical
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def kendall_tau(ranks_a: list[tuple[str, int]], ranks_b: list[tuple[str, int]]) -> float:
    """
    Kendall's Tau rank correlation between two ranked brand lists.

    Only considers brands that appear in BOTH lists.
    Returns correlation in [-1, 1]. 1.0 = identical ranking.
    """
    # Find common brands
    brands_a = {brand: rank for brand, rank in ranks_a}
    brands_b = {brand: rank for brand, rank in ranks_b}
    common = set(brands_a.keys()) & set(brands_b.keys())

    if len(common) < 2:
        return np.nan  # Need at least 2 common brands

    ranks_x = [brands_a[b] for b in sorted(common)]
    ranks_y = [brands_b[b] for b in sorted(common)]

    tau, _ = stats.kendalltau(ranks_x, ranks_y)
    return float(tau)


def rank_biased_overlap(list_a: list[str], list_b: list[str], p: float = 0.9) -> float:
    """
    Rank-Biased Overlap (RBO) — a top-weighted rank similarity measure.

    Unlike Kendall's Tau, RBO:
    - Handles lists of different lengths
    - Weights top positions more heavily
    - Works with incomplete rankings

    Args:
        list_a: Ordered list of brand names (position 1 first)
        list_b: Ordered list of brand names (position 1 first)
        p: Persistence parameter (0-1). Higher = more weight on deeper positions.
             p=0.9 means ~86% of the weight is on the top 10 items.

    Returns:
        RBO score in [0, 1]. 1.0 = identical rankings.
    """
    if not list_a and not list_b:
        return 1.0
    if not list_a or not list_b:
        return 0.0

    min_len = min(len(list_a), len(list_b))
    max_len = max(len(list_a), len(list_b))

    # Calculate agreement at each depth d
    rbo_sum = 0.0
    intersection_size = 0

    set_a = set()
    set_b = set()

    for d in range(1, max_len + 1):
        if d <= len(list_a):
            set_a.add(list_a[d - 1])
        if d <= len(list_b):
            set_b.add(list_b[d - 1])

        intersection_size = len(set_a & set_b)
        agreement = intersection_size / d
        rbo_sum += (p ** (d - 1)) * agreement

    rbo = (1 - p) * rbo_sum
    return float(rbo)


# ===========================================================================
# Mention consistency
# ===========================================================================

def mention_consistency(runs_data: pd.DataFrame, brand_col: str = "brand") -> pd.DataFrame:
    """
    Calculate how consistently each brand is mentioned across runs.

    Returns a DataFrame with:
    - brand: Brand name
    - n_runs: Total runs
    - n_mentioned: Times mentioned
    - consistency_pct: Percentage of runs where brand was mentioned
    - stability: "stable" (>80%), "moderate" (50-80%), "unstable" (<50%)
    """
    consistency = (
        runs_data.groupby(brand_col)
        .agg(
            n_runs=("brand_found", "count"),
            n_mentioned=("brand_found", "sum"),
        )
        .reset_index()
    )
    consistency["consistency_pct"] = (consistency["n_mentioned"] / consistency["n_runs"] * 100).round(1)
    consistency["stability"] = consistency["consistency_pct"].apply(
        lambda x: "stable" if x >= 80 else "moderate" if x >= 50 else "unstable"
    )
    return consistency.sort_values("consistency_pct", ascending=False)


# ===========================================================================
# Fleiss' Kappa (inter-rater agreement)
# ===========================================================================

def fleiss_kappa(ratings_matrix: np.ndarray) -> float:
    """
    Fleiss' Kappa for measuring agreement among multiple raters (runs).

    Each run is treated as a "rater" that either mentions (1) or doesn't mention (0) a brand.

    Args:
        ratings_matrix: shape (n_subjects, n_categories)
            For binary mention: n_categories=2, columns=[not_mentioned_count, mentioned_count]

    Returns:
        Kappa in [-1, 1].
        - 1.0 = perfect agreement
        - 0.0 = agreement expected by chance
        - < 0 = less than chance agreement
    """
    n_subjects, n_categories = ratings_matrix.shape
    n_raters = ratings_matrix.sum(axis=1)[0]  # Assumes same number of raters per subject

    if n_raters <= 1:
        return np.nan

    # Proportion of raters in each category
    p_j = ratings_matrix.sum(axis=0) / (n_subjects * n_raters)

    # Agreement per subject
    P_i = (np.sum(ratings_matrix ** 2, axis=1) - n_raters) / (n_raters * (n_raters - 1))

    P_bar = np.mean(P_i)
    P_e = np.sum(p_j ** 2)

    if P_e == 1.0:
        return 1.0  # Perfect agreement by definition

    kappa = (P_bar - P_e) / (1 - P_e)
    return float(kappa)


def compute_fleiss_kappa_for_prompt(
    prompt_data: pd.DataFrame,
    brands: list[str],
) -> float:
    """
    Compute Fleiss' Kappa for a single prompt across all runs.

    Each brand is a "subject", each run is a "rater".
    Binary categories: mentioned (1) or not mentioned (0).
    """
    n_runs = prompt_data["run_id"].nunique()

    # Build ratings matrix: rows = brands, columns = [not_mentioned, mentioned]
    matrix = []
    for brand in brands:
        brand_data = prompt_data[prompt_data["brand"] == brand]
        n_mentioned = int(brand_data["brand_found"].sum())
        n_not_mentioned = n_runs - n_mentioned
        matrix.append([n_not_mentioned, n_mentioned])

    ratings = np.array(matrix)
    return fleiss_kappa(ratings)


# ===========================================================================
# Full similarity analysis
# ===========================================================================

def run_similarity_analysis(
    metrics_df: pd.DataFrame,
    output_dir: str | Path | None = None,
) -> dict:
    """
    Run the full similarity analysis across all prompts and models.

    Returns dict with DataFrames:
    - pairwise_jaccard: Jaccard similarity between all run pairs
    - pairwise_rbo: RBO between all run pairs
    - mention_consistency: Brand consistency per prompt/model
    - prompt_stability: Overall stability score per prompt
    - fleiss_kappa: Agreement scores per prompt
    """
    output_dir = Path(output_dir) if output_dir else Path("results")
    output_dir.mkdir(parents=True, exist_ok=True)

    brands = sorted(metrics_df["brand"].unique())
    results = {}

    # ----- 1. Pairwise Jaccard & RBO per prompt x model -----
    pairwise_records = []

    for (prompt_id, model), group in metrics_df.groupby(["prompt_id", "model"]):
        runs = sorted(group["run_id"].unique())
        if len(runs) < 2:
            continue

        # Build brand sets and rank lists per run
        run_brands = {}
        run_ranks = {}
        for run_id in runs:
            run_data = group[group["run_id"] == run_id]
            mentioned = set(run_data[run_data["brand_found"] == 1]["brand"].values)
            run_brands[run_id] = mentioned

            # Build ranked list (sorted by rank_position)
            ranked = (
                run_data[run_data["rank_position"] < 999]
                .sort_values("rank_position")["brand"]
                .tolist()
            )
            run_ranks[run_id] = ranked

        # Compute pairwise similarities
        for r_a, r_b in combinations(runs, 2):
            jacc = jaccard_similarity(run_brands[r_a], run_brands[r_b])
            rbo_val = rank_biased_overlap(run_ranks[r_a], run_ranks[r_b])
            tau = kendall_tau(
                [(b, i) for i, b in enumerate(run_ranks[r_a])],
                [(b, i) for i, b in enumerate(run_ranks[r_b])],
            )

            pairwise_records.append({
                "prompt_id": prompt_id,
                "model": model,
                "run_a": r_a,
                "run_b": r_b,
                "jaccard": jacc,
                "rbo": rbo_val,
                "kendall_tau": tau,
            })

    pairwise_df = pd.DataFrame(pairwise_records)
    pairwise_df.to_csv(output_dir / "pairwise_similarity.csv", index=False)
    results["pairwise"] = pairwise_df

    # ----- 2. Mention consistency per brand x prompt x model -----
    consistency_records = []
    for (prompt_id, model), group in metrics_df.groupby(["prompt_id", "model"]):
        cons = mention_consistency(group)
        cons["prompt_id"] = prompt_id
        cons["model"] = model
        consistency_records.append(cons)

    if consistency_records:
        consistency_df = pd.concat(consistency_records, ignore_index=True)
        consistency_df.to_csv(output_dir / "mention_consistency.csv", index=False)
        results["consistency"] = consistency_df

    # ----- 3. Prompt stability scores -----
    if not pairwise_df.empty:
        stability = (
            pairwise_df.groupby(["prompt_id", "model"])
            .agg(
                mean_jaccard=("jaccard", "mean"),
                std_jaccard=("jaccard", "std"),
                mean_rbo=("rbo", "mean"),
                std_rbo=("rbo", "std"),
                mean_kendall=("kendall_tau", "mean"),
                n_pairs=("jaccard", "count"),
            )
            .reset_index()
        )
        stability["stability_label"] = stability["mean_jaccard"].apply(
            lambda x: "high" if x >= 0.8 else "moderate" if x >= 0.5 else "low"
        )
        stability.to_csv(output_dir / "prompt_stability.csv", index=False)
        results["stability"] = stability

    # ----- 4. Fleiss' Kappa per prompt x model -----
    kappa_records = []
    for (prompt_id, model), group in metrics_df.groupby(["prompt_id", "model"]):
        kappa = compute_fleiss_kappa_for_prompt(group, brands)
        kappa_records.append({
            "prompt_id": prompt_id,
            "model": model,
            "fleiss_kappa": kappa,
        })

    kappa_df = pd.DataFrame(kappa_records)
    kappa_df.to_csv(output_dir / "fleiss_kappa.csv", index=False)
    results["kappa"] = kappa_df

    # ----- 5. Summary -----
    logger.info("Similarity Analysis Summary:")
    if not pairwise_df.empty:
        logger.info(f"  Mean Jaccard: {pairwise_df['jaccard'].mean():.3f} (1.0 = identical brand sets)")
        logger.info(f"  Mean RBO:     {pairwise_df['rbo'].mean():.3f} (1.0 = identical rankings)")
        logger.info(f"  Mean Tau:     {pairwise_df['kendall_tau'].dropna().mean():.3f} (1.0 = identical order)")
    if not kappa_df.empty:
        logger.info(f"  Mean Kappa:   {kappa_df['fleiss_kappa'].dropna().mean():.3f} (1.0 = perfect agreement)")

    return results


# ===========================================================================
# CLI
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="Similarity Analysis Between Prompt Runs")
    parser.add_argument("--input", type=str, default="data/parsed_metrics.csv", help="Parsed metrics CSV")
    parser.add_argument("--output-dir", type=str, default="results", help="Output directory")
    args = parser.parse_args()

    df = pd.read_csv(args.input, encoding="utf-8")
    run_similarity_analysis(df, args.output_dir)


if __name__ == "__main__":
    main()
