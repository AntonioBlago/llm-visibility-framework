"""Data collector: sends prompts to Claude, GPT-4o, and Gemini concurrently.

Uses ThreadPoolExecutor to call all 3 models in parallel for each prompt+run,
cutting total collection time by ~3x. Each model runs in its own thread.
File writes are thread-safe via a lock.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger
from tqdm import tqdm

from src.config import StudyConfig, load_all_prompts, ModelConfig


# ---------------------------------------------------------------------------
# Provider-specific API call wrappers
# ---------------------------------------------------------------------------

def _call_anthropic(prompt: str, cfg: ModelConfig) -> str:
    """Call Anthropic Claude API."""
    import anthropic

    client = anthropic.Anthropic(api_key=cfg.api_key)
    response = client.messages.create(
        model=cfg.model_id,
        max_tokens=cfg.max_tokens,
        temperature=cfg.temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _call_openai(prompt: str, cfg: ModelConfig) -> str:
    """Call OpenAI GPT API."""
    import openai

    client = openai.OpenAI(api_key=cfg.api_key)
    response = client.chat.completions.create(
        model=cfg.model_id,
        max_tokens=cfg.max_tokens,
        temperature=cfg.temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


def _call_google(prompt: str, cfg: ModelConfig) -> str:
    """Call Google Gemini API."""
    import google.generativeai as genai

    genai.configure(api_key=cfg.api_key)
    model = genai.GenerativeModel(
        cfg.model_id,
        generation_config=genai.GenerationConfig(
            temperature=cfg.temperature,
            max_output_tokens=cfg.max_tokens,
        ),
    )
    response = model.generate_content(prompt)
    return response.text


PROVIDERS = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
    "google": _call_google,
}


# ---------------------------------------------------------------------------
# Single model call with retry
# ---------------------------------------------------------------------------

def call_model(
    prompt: str,
    model_name: str,
    model_cfg: ModelConfig,
    max_retries: int = 3,
    retry_delay: float = 5.0,
) -> dict[str, Any]:
    """Send a single prompt to a model with retries on transient errors."""
    provider_fn = PROVIDERS.get(model_cfg.provider)
    if not provider_fn:
        raise ValueError(f"Unknown provider: {model_cfg.provider}")

    last_error = None
    for attempt in range(1, max_retries + 1):
        start = time.time()
        try:
            response_text = provider_fn(prompt, model_cfg)
            elapsed = time.time() - start
            return {
                "model": model_name,
                "model_id": model_cfg.model_id,
                "provider": model_cfg.provider,
                "temperature": model_cfg.temperature,
                "response": response_text,
                "latency_s": round(elapsed, 3),
                "error": None,
            }
        except Exception as e:
            last_error = e
            elapsed = time.time() - start
            if attempt < max_retries:
                wait = retry_delay * attempt
                logger.warning(f"Retry {attempt}/{max_retries} for {model_name}: {e} (waiting {wait:.0f}s)")
                time.sleep(wait)
            else:
                logger.error(f"Failed after {max_retries} retries for {model_name}: {e}")

    return {
        "model": model_name,
        "model_id": model_cfg.model_id,
        "provider": model_cfg.provider,
        "temperature": model_cfg.temperature,
        "response": "",
        "latency_s": round(time.time() - start, 3),
        "error": str(last_error),
    }


# ---------------------------------------------------------------------------
# Thread-safe file writer
# ---------------------------------------------------------------------------

class SafeJsonlWriter:
    """Thread-safe JSONL appender."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()

    def write(self, record: dict) -> None:
        with self.lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Parallel collection: all 3 models called concurrently per prompt+run
# ---------------------------------------------------------------------------

def _collect_one_prompt_run(
    prompt_data: dict,
    run_idx: int,
    model_name: str,
    model_cfg: ModelConfig,
) -> dict[str, Any]:
    """Worker function: call one model for one prompt+run. Runs in a thread."""
    result = call_model(prompt_data["text"], model_name, model_cfg)
    return {
        "prompt_id": prompt_data["id"],
        "prompt_text": prompt_data["text"],
        "cluster": prompt_data.get("cluster", "unknown"),
        "model": result["model"],
        "model_id": result["model_id"],
        "provider": result["provider"],
        "temperature": result["temperature"],
        "run_id": run_idx,
        "response": result["response"],
        "latency_s": result["latency_s"],
        "error": result["error"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def collect_data(
    num_runs: int = 30,
    models: list[str] | None = None,
    clusters: list[str] | None = None,
    output_path: Path | None = None,
    delay_between_calls: float = 0.3,
    max_workers: int = 6,
) -> pd.DataFrame:
    """
    Run parallel data collection.

    For each prompt x run, calls all models concurrently using ThreadPoolExecutor.
    With 3 models and max_workers=6, up to 6 API calls run simultaneously.
    """
    cfg = StudyConfig.load()
    prompts = load_all_prompts(clusters)
    model_names = models or list(cfg.models.keys())
    output_path = output_path or cfg.data_dir / "raw_responses.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Filter models with valid API keys
    active_models = {}
    for name in model_names:
        mcfg = cfg.models[name]
        if mcfg.api_key:
            active_models[name] = mcfg
        else:
            logger.warning(f"No API key for {name}, skipping")

    total = len(prompts) * len(active_models) * num_runs
    logger.info(
        f"Starting parallel collection: {len(prompts)} prompts x {len(active_models)} models "
        f"x {num_runs} runs = {total} API calls (max_workers={max_workers})"
    )

    writer = SafeJsonlWriter(output_path)
    records: list[dict[str, Any]] = []
    records_lock = threading.Lock()

    with tqdm(total=total, desc="Collecting", unit="call") as pbar:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Process prompts in order, but parallelize across models + runs
            for prompt_data in prompts:
                # Submit all models x runs for this prompt concurrently
                futures = {}
                for run_idx in range(1, num_runs + 1):
                    for model_name, model_cfg in active_models.items():
                        future = executor.submit(
                            _collect_one_prompt_run,
                            prompt_data, run_idx, model_name, model_cfg,
                        )
                        futures[future] = (prompt_data["id"], model_name, run_idx)

                # Collect results as they complete
                for future in as_completed(futures):
                    prompt_id, model_name, run_idx = futures[future]
                    try:
                        record = future.result()
                    except Exception as e:
                        logger.error(f"Unexpected error for {prompt_id}/{model_name}/run{run_idx}: {e}")
                        record = {
                            "prompt_id": prompt_id,
                            "prompt_text": prompt_data["text"],
                            "cluster": prompt_data.get("cluster", "unknown"),
                            "model": model_name,
                            "model_id": "",
                            "provider": "",
                            "temperature": 0.7,
                            "run_id": run_idx,
                            "response": "",
                            "latency_s": 0,
                            "error": str(e),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }

                    # Thread-safe write + append
                    writer.write(record)
                    with records_lock:
                        records.append(record)
                    pbar.update(1)

                # Small delay between prompts to avoid burst rate limits
                if delay_between_calls > 0:
                    time.sleep(delay_between_calls)

    df = pd.DataFrame(records)
    logger.info(f"Collection complete: {len(df)} records saved to {output_path}")

    # Save CSV
    csv_path = output_path.with_suffix(".csv")
    df.to_csv(csv_path, index=False, encoding="utf-8")
    logger.info(f"CSV saved to {csv_path}")

    # Summary
    error_count = df["error"].notna().sum()
    if error_count > 0:
        logger.warning(f"Errors: {error_count}/{len(df)} calls failed")
        for model in df["model"].unique():
            model_errors = df[(df["model"] == model) & (df["error"].notna())]
            if len(model_errors) > 0:
                logger.warning(f"  {model}: {len(model_errors)} errors")

    return df


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LLM Visibility Study — Parallel Data Collector")
    parser.add_argument("--runs", type=int, default=30, help="Number of runs per prompt per model")
    parser.add_argument("--models", nargs="+", default=None, help="Models to query (default: all)")
    parser.add_argument("--clusters", nargs="+", default=None, help="Prompt clusters (default: all)")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay between prompt batches in seconds")
    parser.add_argument("--workers", type=int, default=6, help="Max concurrent API calls")
    parser.add_argument("--output", type=str, default=None, help="Output file path")

    parser.add_argument("--no-report", action="store_true", help="Skip auto-generating reports after collection")

    args = parser.parse_args()
    output_path = Path(args.output) if args.output else None

    raw_df = collect_data(
        num_runs=args.runs,
        models=args.models,
        clusters=args.clusters,
        output_path=output_path,
        delay_between_calls=args.delay,
        max_workers=args.workers,
    )

    if not args.no_report and not raw_df.empty:
        _run_full_pipeline(raw_df)


def _run_full_pipeline(raw_df: pd.DataFrame) -> None:
    """Auto-run parse -> analyze -> report after collection."""
    from src.config import StudyConfig
    cfg = StudyConfig.load()

    logger.info("=" * 60)
    logger.info("PIPELINE: Auto-generating reports...")
    logger.info("=" * 60)

    # Step 1: Parse responses -> brand metrics
    logger.info("[1/4] Parsing responses for brand mentions...")
    from src.parser import parse_all_responses
    metrics_df = parse_all_responses(raw_df)
    metrics_path = cfg.data_dir / "parsed_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False, encoding="utf-8")
    logger.info(f"  Saved {len(metrics_df)} metrics to {metrics_path}")

    # Step 2: Statistical analysis
    logger.info("[2/4] Running statistical analysis...")
    from src.analyzer import run_full_analysis
    run_full_analysis(str(metrics_path), str(cfg.results_dir))

    # Step 3: Markdown report
    logger.info("[3/4] Generating summary report...")
    from src.report import generate_report
    generate_report(metrics_df, cfg.results_dir)

    # Step 4: HTML report
    logger.info("[4/4] Generating interactive HTML report...")
    from src.report_html import generate_html_report
    html_path = generate_html_report(metrics_df, cfg.results_dir / "report.html")

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info(f"  Markdown:  {cfg.results_dir / 'REPORT.md'}")
    logger.info(f"  HTML:      {html_path}")
    logger.info(f"  CSV data:  {cfg.results_dir}/")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
