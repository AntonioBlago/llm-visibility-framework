"""API cost calculator for LLM visibility studies.

Estimates total cost based on:
- Number of prompts, runs, and models
- Average input/output token counts
- Provider pricing (updated April 2026)

Usage:
    python -m src.cost_calculator --prompts 200 --runs 30
    python -m src.cost_calculator --prompts 100 --runs 20 --models claude gpt
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Pricing per 1M tokens (as of April 2026)
# ---------------------------------------------------------------------------

@dataclass
class ModelPricing:
    name: str
    provider: str
    input_per_1m: float   # USD per 1M input tokens
    output_per_1m: float  # USD per 1M output tokens
    avg_input_tokens: int = 80    # Average tokens per prompt
    avg_output_tokens: int = 600  # Average tokens per response


PRICING = {
    "claude": ModelPricing(
        name="Claude Sonnet 4",
        provider="Anthropic",
        input_per_1m=3.00,
        output_per_1m=15.00,
        avg_input_tokens=80,
        avg_output_tokens=600,
    ),
    "gpt": ModelPricing(
        name="GPT-4o",
        provider="OpenAI",
        input_per_1m=2.50,
        output_per_1m=10.00,
        avg_input_tokens=80,
        avg_output_tokens=600,
    ),
    "gemini": ModelPricing(
        name="Gemini 1.5 Pro",
        provider="Google",
        input_per_1m=1.25,
        output_per_1m=5.00,
        avg_input_tokens=80,
        avg_output_tokens=600,
    ),
}


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

def calculate_cost(
    n_prompts: int = 200,
    n_runs: int = 30,
    models: list[str] | None = None,
    avg_input_tokens: int | None = None,
    avg_output_tokens: int | None = None,
) -> dict:
    """
    Calculate estimated API cost for a visibility study.

    Returns dict with per-model and total costs.
    """
    models = models or list(PRICING.keys())
    results = {
        "n_prompts": n_prompts,
        "n_runs": n_runs,
        "n_models": len(models),
        "total_api_calls": n_prompts * n_runs * len(models),
        "models": {},
        "total_cost_usd": 0.0,
    }

    for model_key in models:
        pricing = PRICING.get(model_key)
        if not pricing:
            continue

        input_tokens = avg_input_tokens or pricing.avg_input_tokens
        output_tokens = avg_output_tokens or pricing.avg_output_tokens

        n_calls = n_prompts * n_runs
        total_input = n_calls * input_tokens
        total_output = n_calls * output_tokens

        input_cost = (total_input / 1_000_000) * pricing.input_per_1m
        output_cost = (total_output / 1_000_000) * pricing.output_per_1m
        model_total = input_cost + output_cost

        results["models"][model_key] = {
            "name": pricing.name,
            "provider": pricing.provider,
            "api_calls": n_calls,
            "input_tokens": total_input,
            "output_tokens": total_output,
            "input_cost_usd": round(input_cost, 2),
            "output_cost_usd": round(output_cost, 2),
            "total_cost_usd": round(model_total, 2),
            "cost_per_call_usd": round(model_total / n_calls, 5),
            "pricing": {
                "input_per_1m": pricing.input_per_1m,
                "output_per_1m": pricing.output_per_1m,
            },
        }
        results["total_cost_usd"] += model_total

    results["total_cost_usd"] = round(results["total_cost_usd"], 2)
    return results


def print_cost_table(
    prompts_list: list[int] | None = None,
    runs_list: list[int] | None = None,
) -> str:
    """Print a cost matrix for different study configurations."""
    prompts_list = prompts_list or [10, 50, 100, 200]
    runs_list = runs_list or [10, 20, 30]

    lines = []
    lines.append("=" * 80)
    lines.append("LLM VISIBILITY STUDY — API COST CALCULATOR")
    lines.append("=" * 80)

    # Per-model pricing
    lines.append("\nModel Pricing (per 1M tokens):")
    lines.append(f"  {'Model':<20} {'Input':>10} {'Output':>10} {'Avg/Call':>12}")
    lines.append(f"  {'-'*52}")
    for key, p in PRICING.items():
        avg_cost = (p.avg_input_tokens / 1e6 * p.input_per_1m +
                    p.avg_output_tokens / 1e6 * p.output_per_1m)
        lines.append(f"  {p.name:<20} ${p.input_per_1m:>8.2f} ${p.output_per_1m:>8.2f} ${avg_cost:>10.5f}")

    # Cost matrix
    lines.append(f"\n{'TOTAL COST (ALL 3 MODELS)':^80}")
    lines.append("-" * 80)
    header = f"  {'':>12}"
    for n_p in prompts_list:
        header += f" | {n_p:>3} prompts"
    lines.append(header)
    lines.append(f"  {'-'*12}" + ("-+-" + "-"*12) * len(prompts_list))

    for n_r in runs_list:
        row = f"  {n_r:>3} runs    "
        for n_p in prompts_list:
            result = calculate_cost(n_prompts=n_p, n_runs=n_r)
            row += f" | ${result['total_cost_usd']:>9.2f}"
        lines.append(row)

    # API calls matrix
    lines.append(f"\n{'API CALLS (ALL 3 MODELS)':^80}")
    lines.append("-" * 80)
    header = f"  {'':>12}"
    for n_p in prompts_list:
        header += f" | {n_p:>3} prompts"
    lines.append(header)
    lines.append(f"  {'-'*12}" + ("-+-" + "-"*12) * len(prompts_list))

    for n_r in runs_list:
        row = f"  {n_r:>3} runs    "
        for n_p in prompts_list:
            calls = n_p * n_r * 3
            row += f" | {calls:>10,}"
        lines.append(row)

    # Per-model breakdown for recommended config
    lines.append(f"\n{'RECOMMENDED CONFIG: 30 runs x 100 prompts':^80}")
    lines.append("=" * 80)
    result = calculate_cost(n_prompts=100, n_runs=30)
    for key, model in result["models"].items():
        lines.append(f"  {model['name']:<20} {model['api_calls']:>6,} calls | "
                      f"Input: ${model['input_cost_usd']:>6.2f} | "
                      f"Output: ${model['output_cost_usd']:>6.2f} | "
                      f"Total: ${model['total_cost_usd']:>7.2f}")
    lines.append(f"  {'':>20} {'':>13} {'':>19} {'':>20} "
                  f"TOTAL: ${result['total_cost_usd']:>7.2f}")

    # Budget-friendly alternatives
    lines.append(f"\n{'BUDGET OPTIONS':^80}")
    lines.append("-" * 80)
    configs = [
        (10, 50, "Quick exploratory"),
        (20, 50, "Budget-friendly"),
        (30, 50, "Minimum viable"),
        (20, 100, "Good balance"),
        (30, 100, "Recommended"),
        (30, 200, "Gold standard"),
    ]
    for n_r, n_p, label in configs:
        result = calculate_cost(n_prompts=n_p, n_runs=n_r)
        lines.append(f"  {label:<20} {n_r:>2} runs x {n_p:>3} prompts = "
                      f"{result['total_api_calls']:>6,} calls = ${result['total_cost_usd']:>7.2f}")

    lines.append("=" * 80)
    lines.append("\nNote: Costs are estimates based on average token counts.")
    lines.append("Actual costs may vary by 10-20% depending on response length.")
    lines.append("Prices as of April 2026 — check provider pricing pages for updates.")

    output = "\n".join(lines)
    print(output)
    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="API Cost Calculator for LLM Visibility Studies")
    parser.add_argument("--prompts", type=int, default=None, help="Number of prompts")
    parser.add_argument("--runs", type=int, default=None, help="Runs per prompt")
    parser.add_argument("--models", nargs="+", default=None, help="Models to include")
    parser.add_argument("--matrix", action="store_true", help="Show full cost matrix")
    args = parser.parse_args()

    if args.matrix or (args.prompts is None and args.runs is None):
        print_cost_table()
    else:
        n_prompts = args.prompts or 200
        n_runs = args.runs or 30
        result = calculate_cost(n_prompts=n_prompts, n_runs=n_runs, models=args.models)

        print(f"\nCost Estimate: {n_prompts} prompts x {n_runs} runs")
        print(f"Total API calls: {result['total_api_calls']:,}")
        print(f"Total cost: ${result['total_cost_usd']:.2f}")
        print()
        for key, model in result["models"].items():
            print(f"  {model['name']}: {model['api_calls']:,} calls = ${model['total_cost_usd']:.2f}")


if __name__ == "__main__":
    main()
