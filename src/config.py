"""Configuration loader for the LLM Visibility Study."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"


@dataclass
class ModelConfig:
    provider: str
    model_id: str
    temperature: float
    max_tokens: int
    api_key: str

    @classmethod
    def from_dict(cls, name: str, d: dict[str, Any]) -> "ModelConfig":
        env_var = d.get("api_key_env", "")
        api_key = os.environ.get(env_var, "")
        return cls(
            provider=d["provider"],
            model_id=d["model_id"],
            temperature=d.get("temperature", 0.7),
            max_tokens=d.get("max_tokens", 2048),
            api_key=api_key,
        )


@dataclass
class BrandConfig:
    name: str
    domain: str
    aliases: list[str]
    category: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BrandConfig":
        return cls(
            name=d["name"],
            domain=d.get("domain", ""),
            aliases=[a.lower() for a in d.get("aliases", [d["name"].lower()])],
            category=d.get("category", ""),
        )


@dataclass
class VisibilityScoring:
    weights: dict[int, int] = field(default_factory=lambda: {
        1: 10, 2: 8, 3: 6, 4: 5, 5: 4,
    })
    mentioned_other: int = 2
    not_mentioned: int = 0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "VisibilityScoring":
        weights = {}
        for k, v in d.items():
            if k.startswith("position_"):
                pos = int(k.replace("position_", ""))
                weights[pos] = v
        return cls(
            weights=weights,
            mentioned_other=d.get("mentioned_other", 2),
            not_mentioned=d.get("not_mentioned", 0),
        )

    def score(self, rank_position: int | None) -> int:
        if rank_position is None or rank_position == 999:
            return self.not_mentioned
        return self.weights.get(rank_position, self.mentioned_other)


@dataclass
class StudyConfig:
    models: dict[str, ModelConfig]
    brands: list[BrandConfig]
    prompt_clusters: list[str]
    runs_default: int
    runs_power_analysis: list[int]
    alpha: float
    bootstrap_n: int
    correction_method: str
    random_seed: int
    scoring: VisibilityScoring
    data_dir: Path
    results_dir: Path
    figures_dir: Path

    @classmethod
    def load(cls, path: Path | None = None) -> "StudyConfig":
        path = path or CONFIG_PATH
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        models = {
            name: ModelConfig.from_dict(name, cfg)
            for name, cfg in raw.get("models", {}).items()
        }
        brands = [BrandConfig.from_dict(b) for b in raw.get("brands", [])]
        analysis = raw.get("analysis", {})
        output = raw.get("output", {})
        runs = raw.get("runs", {})

        return cls(
            models=models,
            brands=brands,
            prompt_clusters=raw.get("prompt_clusters", []),
            runs_default=runs.get("default", 30),
            runs_power_analysis=runs.get("power_analysis", [10, 20, 30]),
            alpha=analysis.get("alpha", 0.05),
            bootstrap_n=analysis.get("bootstrap_n", 5000),
            correction_method=analysis.get("multiple_testing_correction", "fdr_bh"),
            random_seed=analysis.get("random_seed", 42),
            scoring=VisibilityScoring.from_dict(raw.get("visibility_scoring", {})),
            data_dir=ROOT_DIR / output.get("data_dir", "data"),
            results_dir=ROOT_DIR / output.get("results_dir", "results"),
            figures_dir=ROOT_DIR / output.get("figures_dir", "results/figures"),
        )


def load_prompts(cluster: str) -> list[dict[str, str]]:
    """Load prompts from a YAML cluster file."""
    path = ROOT_DIR / "prompts" / f"{cluster}.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("prompts", [])


def load_all_prompts(clusters: list[str] | None = None) -> list[dict[str, str]]:
    """Load all prompts from all cluster files, adding cluster field."""
    cfg = StudyConfig.load()
    clusters = clusters or cfg.prompt_clusters
    all_prompts = []
    for cluster in clusters:
        prompts = load_prompts(cluster)
        for p in prompts:
            p["cluster"] = cluster
        all_prompts.extend(prompts)
    return all_prompts
