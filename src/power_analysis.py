"""Power analysis: simulates statistical power across runs x prompts matrix.

Answers the core question: How many runs AND how many prompts
are needed to reliably measure brand visibility and rankings?

Matrix tested:
- Runs per prompt: 10, 20, 30
- Number of prompts: 10, 50, 100, 200
- Effect sizes: tiny (3pp), small (5pp), medium (15pp), large (25pp)

Key insight: total observations = runs x prompts.
The combination determines power, not either factor alone.

All prompts are GENERIC (no brand names mentioned) — brands are only
detected in the LLM output, never prompted.
"""

from __future__ import annotations

import argparse
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger
from scipy import stats

from src.analyzer import cliffs_delta, interpret_cliffs_delta


# ===========================================================================
# Simulation engine
# ===========================================================================

def simulate_binary_power(
    p_a: float,
    p_b: float,
    n_per_group: int,
    n_simulations: int = 10000,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict:
    """
    Monte Carlo power simulation for Fisher's exact test on binary outcomes.

    Simulates the probability of detecting a real difference between
    two mention rates (p_a vs p_b) given n_per_group samples per condition.
    """
    rng = np.random.default_rng(seed)
    significant_count = 0

    for _ in range(n_simulations):
        a_samples = rng.binomial(1, p_a, size=n_per_group)
        b_samples = rng.binomial(1, p_b, size=n_per_group)

        a_found = int(a_samples.sum())
        a_not = n_per_group - a_found
        b_found = int(b_samples.sum())
        b_not = n_per_group - b_found

        table = np.array([[a_found, a_not], [b_found, b_not]])
        _, p_value = stats.fisher_exact(table)

        if p_value < alpha:
            significant_count += 1

    power = significant_count / n_simulations
    return {
        "metric": "mention_rate",
        "test": "fisher_exact",
        "p_a": p_a,
        "p_b": p_b,
        "true_diff_pp": round(abs(p_b - p_a) * 100, 1),
        "n_per_group": n_per_group,
        "power": power,
        "alpha": alpha,
    }


def simulate_ordinal_power(
    dist_a: tuple[float, float],
    dist_b: tuple[float, float],
    n_per_group: int,
    n_simulations: int = 10000,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict:
    """
    Monte Carlo power simulation for Mann-Whitney U test on rank data.

    Uses log-normal distributions to simulate realistic rank positions
    (right-skewed: most brands rank low, few rank #1).
    """
    rng = np.random.default_rng(seed)
    significant_count = 0
    deltas = []

    for _ in range(n_simulations):
        a_samples = np.clip(rng.lognormal(dist_a[0], dist_a[1], size=n_per_group), 1, 999)
        b_samples = np.clip(rng.lognormal(dist_b[0], dist_b[1], size=n_per_group), 1, 999)

        _, p_value = stats.mannwhitneyu(a_samples, b_samples, alternative="two-sided")
        delta = cliffs_delta(a_samples, b_samples)
        deltas.append(delta)

        if p_value < alpha:
            significant_count += 1

    return {
        "metric": "rank_position",
        "test": "mann_whitney_u",
        "dist_a_mu": dist_a[0],
        "dist_b_mu": dist_b[0],
        "n_per_group": n_per_group,
        "power": significant_count / n_simulations,
        "mean_cliffs_delta": float(np.mean(deltas)),
        "delta_interpretation": interpret_cliffs_delta(float(np.mean(deltas))),
        "alpha": alpha,
    }


def simulate_visibility_score_power(
    mean_a: float,
    std_a: float,
    mean_b: float,
    std_b: float,
    n_per_group: int,
    n_simulations: int = 10000,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict:
    """Power simulation for visibility score differences (0-10 scale)."""
    rng = np.random.default_rng(seed)
    significant_count = 0

    for _ in range(n_simulations):
        a_samples = np.clip(rng.normal(mean_a, std_a, size=n_per_group), 0, 10)
        b_samples = np.clip(rng.normal(mean_b, std_b, size=n_per_group), 0, 10)

        _, p_value = stats.mannwhitneyu(a_samples, b_samples, alternative="two-sided")

        if p_value < alpha:
            significant_count += 1

    return {
        "metric": "visibility_score",
        "test": "mann_whitney_u",
        "mean_a": mean_a,
        "mean_b": mean_b,
        "true_diff": abs(mean_b - mean_a),
        "n_per_group": n_per_group,
        "power": significant_count / n_simulations,
        "alpha": alpha,
    }


# ===========================================================================
# Full runs x prompts matrix
# ===========================================================================

def run_power_matrix(
    runs_list: list[int] | None = None,
    prompts_list: list[int] | None = None,
    n_simulations: int = 10000,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Run power analysis across the full runs x prompts matrix.

    For each combination, simulates whether the study design
    has sufficient power to detect real brand visibility differences.

    Args:
        runs_list: Number of runs per prompt to test [10, 20, 30]
        prompts_list: Number of prompts to test [10, 50, 100, 200]
        n_simulations: Monte Carlo iterations per scenario
        seed: Random seed for reproducibility
    """
    runs_list = runs_list or [10, 20, 30]
    prompts_list = prompts_list or [10, 50, 100, 200]

    # Effect size scenarios for MENTION RATE (binary)
    mention_scenarios = [
        {"name": "tiny_3pp", "p_a": 0.50, "p_b": 0.53, "label": "3pp (0.50 vs 0.53)"},
        {"name": "small_5pp", "p_a": 0.30, "p_b": 0.35, "label": "5pp (0.30 vs 0.35)"},
        {"name": "small_10pp", "p_a": 0.30, "p_b": 0.40, "label": "10pp (0.30 vs 0.40)"},
        {"name": "medium_15pp", "p_a": 0.30, "p_b": 0.45, "label": "15pp (0.30 vs 0.45)"},
        {"name": "large_25pp", "p_a": 0.30, "p_b": 0.55, "label": "25pp (0.30 vs 0.55)"},
        {"name": "low_base_15pp", "p_a": 0.10, "p_b": 0.25, "label": "15pp from low base (0.10 vs 0.25)"},
    ]

    # Effect size scenarios for RANK POSITION (ordinal)
    rank_scenarios = [
        {"name": "rank_small", "dist_a": (2.0, 1.0), "dist_b": (1.8, 1.0), "label": "Small rank shift"},
        {"name": "rank_medium", "dist_a": (2.0, 1.0), "dist_b": (1.5, 1.0), "label": "Medium rank shift"},
        {"name": "rank_large", "dist_a": (2.5, 1.0), "dist_b": (1.5, 1.0), "label": "Large rank shift"},
    ]

    # Effect size scenarios for VISIBILITY SCORE (continuous 0-10)
    score_scenarios = [
        {"name": "score_small", "mean_a": 3.0, "std_a": 2.5, "mean_b": 3.5, "std_b": 2.5, "label": "0.5pt diff (3.0 vs 3.5)"},
        {"name": "score_medium", "mean_a": 3.0, "std_a": 2.5, "mean_b": 4.5, "std_b": 2.5, "label": "1.5pt diff (3.0 vs 4.5)"},
        {"name": "score_large", "mean_a": 2.0, "std_a": 2.0, "mean_b": 5.0, "std_b": 2.5, "label": "3.0pt diff (2.0 vs 5.0)"},
    ]

    results = []
    total_combos = len(runs_list) * len(prompts_list) * (len(mention_scenarios) + len(rank_scenarios) + len(score_scenarios))
    logger.info(f"Running {total_combos} power simulations ({n_simulations} MC iterations each)...")

    for n_runs, n_prompts in product(runs_list, prompts_list):
        n_per_group = n_runs * n_prompts
        total_api_calls = n_per_group * 3  # 3 models

        # Mention rate scenarios
        for scenario in mention_scenarios:
            result = simulate_binary_power(
                p_a=scenario["p_a"],
                p_b=scenario["p_b"],
                n_per_group=n_per_group,
                n_simulations=n_simulations,
                seed=seed,
            )
            result["n_runs"] = n_runs
            result["n_prompts"] = n_prompts
            result["n_observations"] = n_per_group
            result["total_api_calls"] = total_api_calls
            result["scenario"] = scenario["name"]
            result["scenario_label"] = scenario["label"]
            results.append(result)

        # Rank scenarios
        for scenario in rank_scenarios:
            result = simulate_ordinal_power(
                dist_a=scenario["dist_a"],
                dist_b=scenario["dist_b"],
                n_per_group=n_per_group,
                n_simulations=n_simulations,
                seed=seed,
            )
            result["n_runs"] = n_runs
            result["n_prompts"] = n_prompts
            result["n_observations"] = n_per_group
            result["total_api_calls"] = total_api_calls
            result["scenario"] = scenario["name"]
            result["scenario_label"] = scenario["label"]
            results.append(result)

        # Visibility score scenarios
        for scenario in score_scenarios:
            result = simulate_visibility_score_power(
                mean_a=scenario["mean_a"],
                std_a=scenario["std_a"],
                mean_b=scenario["mean_b"],
                std_b=scenario["std_b"],
                n_per_group=n_per_group,
                n_simulations=n_simulations,
                seed=seed,
            )
            result["n_runs"] = n_runs
            result["n_prompts"] = n_prompts
            result["n_observations"] = n_per_group
            result["total_api_calls"] = total_api_calls
            result["scenario"] = scenario["name"]
            result["scenario_label"] = scenario["label"]
            results.append(result)

    df = pd.DataFrame(results)
    logger.info(f"Power analysis complete: {len(df)} results")
    return df


# ===========================================================================
# Summary and recommendations
# ===========================================================================

def print_power_matrix(df: pd.DataFrame) -> str:
    """Print the runs x prompts power matrix as a readable table."""
    lines = []
    lines.append("=" * 100)
    lines.append("POWER ANALYSIS: Runs x Prompts Matrix")
    lines.append("Question: Is the study design sufficient to measure brand visibility?")
    lines.append("=" * 100)

    # Group by metric type
    for metric in df["metric"].unique():
        metric_df = df[df["metric"] == metric]
        lines.append(f"\n{'=' * 80}")
        lines.append(f"METRIC: {metric.upper()}")
        lines.append(f"{'=' * 80}")

        for scenario in metric_df["scenario"].unique():
            scenario_df = metric_df[metric_df["scenario"] == scenario]
            label = scenario_df.iloc[0].get("scenario_label", scenario)
            lines.append(f"\n  Scenario: {label}")
            lines.append(f"  {'':>12} | {'10 prompts':>12} | {'50 prompts':>12} | {'100 prompts':>12} | {'200 prompts':>12}")
            lines.append(f"  {'-' * 12}-+-{'-' * 12}-+-{'-' * 12}-+-{'-' * 12}-+-{'-' * 12}")

            for n_runs in sorted(scenario_df["n_runs"].unique()):
                row_data = []
                for n_prompts in [10, 50, 100, 200]:
                    match = scenario_df[
                        (scenario_df["n_runs"] == n_runs) & (scenario_df["n_prompts"] == n_prompts)
                    ]
                    if not match.empty:
                        power = match.iloc[0]["power"]
                        marker = "+++" if power >= 0.90 else "++" if power >= 0.80 else "+" if power >= 0.60 else "---"
                        row_data.append(f"{power:>5.1%} {marker:>4}")
                    else:
                        row_data.append(f"{'N/A':>10}")

                lines.append(f"  {n_runs:>3} runs     | {row_data[0]:>12} | {row_data[1]:>12} | {row_data[2]:>12} | {row_data[3]:>12}")

    # Cost summary
    lines.append(f"\n{'=' * 80}")
    lines.append("TOTAL API CALLS (3 models)")
    lines.append(f"{'=' * 80}")
    lines.append(f"  {'':>12} | {'10 prompts':>12} | {'50 prompts':>12} | {'100 prompts':>12} | {'200 prompts':>12}")
    lines.append(f"  {'-' * 12}-+-{'-' * 12}-+-{'-' * 12}-+-{'-' * 12}-+-{'-' * 12}")
    for n_runs in [10, 20, 30]:
        calls = [n_runs * n_p * 3 for n_p in [10, 50, 100, 200]]
        lines.append(
            f"  {n_runs:>3} runs     | {calls[0]:>10,}   | {calls[1]:>10,}   | {calls[2]:>10,}   | {calls[3]:>10,}  "
        )

    # Recommendations
    lines.append(f"\n{'=' * 80}")
    lines.append("RECOMMENDATIONS")
    lines.append(f"{'=' * 80}")
    lines.append("")
    lines.append("  For MENTION RATE (primary metric):")
    lines.append("    Minimum viable:  30 runs x 50 prompts  = 1,500 obs/model (4,500 API calls)")
    lines.append("    Recommended:     30 runs x 100 prompts = 3,000 obs/model (9,000 API calls)")
    lines.append("    Gold standard:   30 runs x 200 prompts = 6,000 obs/model (18,000 API calls)")
    lines.append("")
    lines.append("  For RANK POSITION (secondary metric):")
    lines.append("    Needs larger samples due to high variance in rank data")
    lines.append("    Minimum viable:  30 runs x 100 prompts")
    lines.append("")
    lines.append("  For VISIBILITY SCORE (secondary metric):")
    lines.append("    Similar requirements to mention rate")
    lines.append("")
    lines.append("  Budget-conscious option:")
    lines.append("    20 runs x 50 prompts = 1,000 obs/model (3,000 API calls)")
    lines.append("    Sufficient for medium-to-large effects only")
    lines.append("")
    lines.append("  IMPORTANT: All prompts must be GENERIC (no brand names).")
    lines.append("  Brands are only detected in the output, never in the prompt.")
    lines.append(f"{'=' * 80}")

    summary = "\n".join(lines)
    print(summary)
    return summary


# ===========================================================================
# Type I Error validation
# ===========================================================================

def validate_type_i_error(
    p_true: float = 0.40,
    n_per_group: int = 300,
    n_simulations: int = 10000,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict:
    """
    Validate that the test maintains correct Type I error rate
    when there is no true difference (H0 is true).
    """
    rng = np.random.default_rng(seed)
    false_positives = 0

    for _ in range(n_simulations):
        a_samples = rng.binomial(1, p_true, size=n_per_group)
        b_samples = rng.binomial(1, p_true, size=n_per_group)

        table = np.array([
            [int(a_samples.sum()), n_per_group - int(a_samples.sum())],
            [int(b_samples.sum()), n_per_group - int(b_samples.sum())],
        ])
        _, p_value = stats.fisher_exact(table)

        if p_value < alpha:
            false_positives += 1

    type_i_rate = false_positives / n_simulations
    return {
        "p_true": p_true,
        "n_per_group": n_per_group,
        "type_i_rate": type_i_rate,
        "expected": alpha,
        "calibrated": abs(type_i_rate - alpha) < 0.02,
    }


# ===========================================================================
# Minimum sample size calculator
# ===========================================================================

def find_minimum_sample_size(
    p_a: float = 0.30,
    p_b: float = 0.45,
    target_power: float = 0.80,
    alpha: float = 0.05,
    n_simulations: int = 5000,
    seed: int = 42,
) -> dict:
    """
    Find the minimum n_per_group needed to achieve target power.

    Uses binary search over sample sizes.
    """
    low, high = 10, 5000
    best_n = high

    while low <= high:
        mid = (low + high) // 2
        result = simulate_binary_power(p_a, p_b, mid, n_simulations=n_simulations, alpha=alpha, seed=seed)

        if result["power"] >= target_power:
            best_n = mid
            high = mid - 1
        else:
            low = mid + 1

    return {
        "p_a": p_a,
        "p_b": p_b,
        "target_power": target_power,
        "min_n_per_group": best_n,
        "example_configs": [
            {"n_runs": 10, "n_prompts": max(1, best_n // 10)},
            {"n_runs": 20, "n_prompts": max(1, best_n // 20)},
            {"n_runs": 30, "n_prompts": max(1, best_n // 30)},
        ],
    }


# ===========================================================================
# CLI
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="Power Analysis: Runs x Prompts Matrix")
    parser.add_argument("--runs", nargs="+", type=int, default=[10, 20, 30], help="Run counts")
    parser.add_argument("--prompts", nargs="+", type=int, default=[10, 50, 100, 200], help="Prompt counts")
    parser.add_argument("--simulations", type=int, default=10000, help="Monte Carlo simulations")
    parser.add_argument("--output", type=str, default="results/power_analysis.csv", help="Output CSV")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Run full matrix
    results = run_power_matrix(
        runs_list=args.runs,
        prompts_list=args.prompts,
        n_simulations=args.simulations,
    )
    results.to_csv(output_path, index=False)
    logger.info(f"Saved to {output_path}")

    # Print matrix
    print_power_matrix(results)

    # Find minimum sample sizes for key scenarios
    print("\n\nMINIMUM SAMPLE SIZE CALCULATOR")
    print("=" * 60)
    for diff_label, p_a, p_b in [
        ("5pp", 0.30, 0.35),
        ("10pp", 0.30, 0.40),
        ("15pp", 0.30, 0.45),
        ("25pp", 0.30, 0.55),
    ]:
        result = find_minimum_sample_size(p_a=p_a, p_b=p_b)
        print(f"\n  {diff_label} difference ({p_a} vs {p_b}):")
        print(f"    Min n per group: {result['min_n_per_group']}")
        for cfg in result["example_configs"]:
            print(f"      {cfg['n_runs']} runs x {cfg['n_prompts']} prompts = {cfg['n_runs'] * cfg['n_prompts']} observations")

    # Type I error validation
    print("\n\nTYPE I ERROR VALIDATION (no true difference)")
    print("=" * 60)
    for n in [100, 300, 1000, 3000]:
        val = validate_type_i_error(n_per_group=n, n_simulations=args.simulations)
        print(f"  n={n:>5}: Type I rate = {val['type_i_rate']:.3f} (expected 0.050) {'PASS' if val['calibrated'] else 'WARN'}")


if __name__ == "__main__":
    main()
