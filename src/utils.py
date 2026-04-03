"""Utility functions for the LLM Visibility Study."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


def load_raw_data(path: str | Path) -> pd.DataFrame:
    """Load raw response data from CSV or JSONL."""
    path = Path(path)
    if path.suffix == ".csv":
        return pd.read_csv(path, encoding="utf-8")
    elif path.suffix == ".jsonl":
        return pd.read_json(path, lines=True)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")


def generate_run_id(prompt_id: str, model: str, run: int) -> str:
    """Generate a deterministic unique ID for a single run."""
    raw = f"{prompt_id}_{model}_{run}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def safe_division(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division avoiding ZeroDivisionError."""
    if denominator == 0:
        return default
    return numerator / denominator
