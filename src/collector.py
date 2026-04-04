"""Data collector: sends prompts to Claude, GPT-4o, and Gemini, stores raw responses."""

from __future__ import annotations

import argparse
import json
import time
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


def call_model(
    prompt: str,
    model_name: str,
    model_cfg: ModelConfig,
    max_retries: int = 3,
    retry_delay: float = 5.0,
) -> dict[str, Any]:
    """Send a single prompt to a model and return structured result. Retries on transient errors."""
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
# Main collection loop
# ---------------------------------------------------------------------------

def collect_data(
    num_runs: int = 30,
    models: list[str] | None = None,
    clusters: list[str] | None = None,
    output_path: Path | None = None,
    delay_between_calls: float = 1.0,
) -> pd.DataFrame:
    """
    Run the full data collection pipeline.

    For each prompt x model x run, sends the prompt and stores the raw response.
    """
    cfg = StudyConfig.load()
    prompts = load_all_prompts(clusters)
    model_names = models or list(cfg.models.keys())
    output_path = output_path or cfg.data_dir / "raw_responses.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = len(prompts) * len(model_names) * num_runs
    logger.info(
        f"Starting collection: {len(prompts)} prompts x {len(model_names)} models "
        f"x {num_runs} runs = {total} API calls"
    )

    records: list[dict[str, Any]] = []

    with tqdm(total=total, desc="Collecting") as pbar:
        for prompt_data in prompts:
            prompt_id = prompt_data["id"]
            prompt_text = prompt_data["text"]
            cluster = prompt_data.get("cluster", "unknown")

            for model_name in model_names:
                model_cfg = cfg.models[model_name]

                if not model_cfg.api_key:
                    logger.warning(f"No API key for {model_name}, skipping")
                    pbar.update(num_runs)
                    continue

                for run_idx in range(1, num_runs + 1):
                    result = call_model(prompt_text, model_name, model_cfg)

                    record = {
                        "prompt_id": prompt_id,
                        "prompt_text": prompt_text,
                        "cluster": cluster,
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
                    records.append(record)

                    # Append to JSONL file incrementally
                    with open(output_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")

                    pbar.update(1)

                    if delay_between_calls > 0:
                        time.sleep(delay_between_calls)

    df = pd.DataFrame(records)
    logger.info(f"Collection complete: {len(df)} records saved to {output_path}")

    # Also save as CSV for convenience
    csv_path = output_path.with_suffix(".csv")
    df.to_csv(csv_path, index=False, encoding="utf-8")
    logger.info(f"CSV saved to {csv_path}")

    return df


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LLM Visibility Study — Data Collector")
    parser.add_argument("--runs", type=int, default=30, help="Number of runs per prompt per model")
    parser.add_argument("--models", nargs="+", default=None, help="Models to query (default: all)")
    parser.add_argument("--clusters", nargs="+", default=None, help="Prompt clusters (default: all)")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between API calls in seconds")
    parser.add_argument("--output", type=str, default=None, help="Output file path")

    args = parser.parse_args()
    output_path = Path(args.output) if args.output else None

    collect_data(
        num_runs=args.runs,
        models=args.models,
        clusters=args.clusters,
        output_path=output_path,
        delay_between_calls=args.delay,
    )


if __name__ == "__main__":
    main()
