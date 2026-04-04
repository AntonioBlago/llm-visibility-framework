"""Response parser: extracts brand mentions, ranking positions, and visibility scores from LLM outputs.

Brand detection strategy (3 layers):
1. Exact match: word-boundary regex against all aliases
2. Domain match: detect brand domains (e.g., "foodspring.de") in text
3. Fuzzy match: thefuzz partial_ratio for typos, compound words, German declensions

A brand is considered "found" if ANY layer matches above its threshold.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from loguru import logger

from src.config import StudyConfig, BrandConfig

# Lazy import for fuzzy matching (optional dependency)
_fuzz = None


def _get_fuzz():
    """Lazy-load thefuzz to avoid import errors if not installed."""
    global _fuzz
    if _fuzz is None:
        try:
            from thefuzz import fuzz as _fuzz_mod
            _fuzz = _fuzz_mod
        except ImportError:
            logger.warning("thefuzz not installed — fuzzy matching disabled. pip install thefuzz")
            _fuzz = False
    return _fuzz if _fuzz else None


@dataclass
class BrandMention:
    """A single brand detection result within one LLM response."""
    brand_name: str
    found: bool
    rank_position: int | None  # 1-based, None if not in a list
    in_top3: bool
    visibility_score: int
    match_text: str  # The actual text that matched
    match_method: str = ""  # "exact", "domain", "fuzzy", or ""
    fuzzy_score: int = 0  # Fuzzy match score (0-100)


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Normalize text for matching: lowercase, collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _normalize_german(text: str) -> str:
    """Normalize German umlauts and special characters for fuzzy matching."""
    replacements = {
        "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
        "ae": "ä", "oe": "ö", "ue": "ü",
    }
    text = text.lower()
    # Don't replace — just normalize for comparison
    return re.sub(r"\s+", " ", text.strip())


# ---------------------------------------------------------------------------
# Layer 1: Exact matching (word-boundary regex)
# ---------------------------------------------------------------------------

def _find_brand_exact(text: str, brand: BrandConfig) -> tuple[bool, str]:
    """Check if any alias of a brand appears with exact word boundaries."""
    text_lower = _normalize(text)

    # Check all aliases + brand name itself
    all_names = brand.aliases + [brand.name.lower()]

    for alias in all_names:
        alias_lower = alias.lower()
        # Word-boundary aware match: not preceded/followed by alphanumeric
        pattern = r"(?<![a-z0-9äöüß])" + re.escape(alias_lower) + r"(?![a-z0-9äöüß])"
        match = re.search(pattern, text_lower)
        if match:
            # Extract context around match
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            return True, text[start:end]

    return False, ""


# ---------------------------------------------------------------------------
# Layer 2: Domain matching
# ---------------------------------------------------------------------------

def _find_brand_domain(text: str, brand: BrandConfig) -> tuple[bool, str]:
    """Check if the brand's domain appears in the text."""
    if not brand.domain:
        return False, ""

    text_lower = text.lower()
    domain_lower = brand.domain.lower()

    # Check for domain with or without www.
    for variant in [domain_lower, f"www.{domain_lower}"]:
        idx = text_lower.find(variant)
        if idx >= 0:
            start = max(0, idx - 20)
            end = min(len(text), idx + len(variant) + 20)
            return True, text[start:end]

    return False, ""


# ---------------------------------------------------------------------------
# Layer 3: Fuzzy matching
# ---------------------------------------------------------------------------

# Short/generic brand names that would cause too many false positives with fuzzy matching
FUZZY_BLOCKLIST = {
    "bite", "more", "holy", "ritual", "sunday", "blume", "form",
    "ahead", "sheko", "lemme",
}


def _find_brand_fuzzy(
    text: str,
    brand: BrandConfig,
    threshold: int = 85,
    partial_threshold: int = 90,
) -> tuple[bool, str, int]:
    """
    Fuzzy match brand names in text using thefuzz.

    Uses partial_ratio for substring matching (handles compound words,
    German declensions like "Foodsprings" or "AG1-Pulver").

    Returns (found, match_text, score).
    """
    fuzz = _get_fuzz()
    if not fuzz:
        return False, "", 0

    text_lower = _normalize(text)

    # Skip fuzzy for very short/generic brand names (high false positive risk)
    all_names = [brand.name.lower()] + [a for a in brand.aliases if a.lower() not in FUZZY_BLOCKLIST]
    all_names = [n for n in all_names if len(n) >= 4]  # Min 4 chars for fuzzy

    if not all_names:
        return False, "", 0

    best_score = 0
    best_match = ""

    # Slide a window across the text to find the best fuzzy match
    # Check each sentence/segment separately for better precision
    segments = re.split(r"[.\n,;:!?]", text_lower)

    for segment in segments:
        segment = segment.strip()
        if len(segment) < 3:
            continue

        for name in all_names:
            # partial_ratio handles substring matching well
            score = fuzz.partial_ratio(name, segment)

            if score >= partial_threshold and score > best_score:
                best_score = score
                # Find approximate location
                idx = segment.find(name[:3])
                if idx >= 0:
                    best_match = segment[max(0, idx - 20):idx + len(name) + 20]
                else:
                    best_match = segment[:60]

            # Also check token_set_ratio for reordered words
            # e.g., "Natural Mojo" vs "Mojo Natural"
            if " " in name:
                score_set = fuzz.token_set_ratio(name, segment)
                if score_set >= threshold and score_set > best_score:
                    best_score = score_set
                    best_match = segment[:60]

    if best_score >= partial_threshold:
        return True, best_match, best_score

    return False, "", best_score


# ---------------------------------------------------------------------------
# Combined brand detection
# ---------------------------------------------------------------------------

def find_brand_in_text(
    text: str,
    brand: BrandConfig,
    fuzzy_enabled: bool = True,
    fuzzy_threshold: int = 85,
    fuzzy_partial_threshold: int = 90,
) -> tuple[bool, str, str, int]:
    """
    Multi-layer brand detection.

    Returns (found, match_text, match_method, fuzzy_score).
    Match methods: "exact", "domain", "fuzzy", "".
    """
    # Layer 1: Exact match (fastest, most reliable)
    found, match_text = _find_brand_exact(text, brand)
    if found:
        return True, match_text, "exact", 100

    # Layer 2: Domain match
    found, match_text = _find_brand_domain(text, brand)
    if found:
        return True, match_text, "domain", 100

    # Layer 3: Fuzzy match (catches typos, compound words, declensions)
    if fuzzy_enabled:
        found, match_text, score = _find_brand_fuzzy(
            text, brand,
            threshold=fuzzy_threshold,
            partial_threshold=fuzzy_partial_threshold,
        )
        if found:
            return True, match_text, "fuzzy", score

    return False, "", "", 0


# ---------------------------------------------------------------------------
# Ranked list extraction
# ---------------------------------------------------------------------------

def _extract_ranked_list(text: str) -> list[str]:
    """
    Extract items from a numbered/bulleted list in the LLM response.

    Handles formats like:
    - 1. Brand Name
    - 1) Brand Name
    - **1. Brand Name**
    - - Brand Name
    - * Brand Name
    - ### Brand Name (markdown headers as list items)
    """
    lines = text.split("\n")
    items = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Numbered list: "1. Item", "1) Item", "1: Item"
        match = re.match(r"^\*{0,2}\s*(\d+)\s*[.):\-]\s*\*{0,2}\s*(.+)", line)
        if match:
            item_text = match.group(2).strip()
            item_text = re.sub(r"\*{1,2}$", "", item_text).strip()
            # Remove description after dash/colon
            item_text_name = re.split(r"\s*[-–—:]\s", item_text)[0].strip()
            items.append(item_text_name if item_text_name else item_text)
            continue

        # Bulleted list: "- Item", "* Item"
        match = re.match(r"^[-*]\s+\*{0,2}\s*(.+)", line)
        if match:
            item_text = match.group(1).strip()
            item_text = re.sub(r"\*{1,2}$", "", item_text).strip()
            item_text_name = re.split(r"\s*[-–—:]\s", item_text)[0].strip()
            items.append(item_text_name if item_text_name else item_text)

    return items


def _find_brand_rank(
    items: list[str],
    brand: BrandConfig,
    fuzzy_enabled: bool = True,
    fuzzy_threshold: int = 85,
) -> int | None:
    """Find the position of a brand in a ranked list. Returns 1-based index or None."""
    fuzz = _get_fuzz() if fuzzy_enabled else None

    for idx, item in enumerate(items, start=1):
        item_lower = _normalize(item)

        # Exact check against aliases + name
        for alias in brand.aliases + [brand.name.lower()]:
            if alias.lower() in item_lower:
                return idx

        # Fuzzy check on list items (more lenient — items are short)
        if fuzz and len(brand.name) >= 4 and brand.name.lower() not in FUZZY_BLOCKLIST:
            for alias in [brand.name.lower()] + brand.aliases:
                if len(alias) < 4 or alias in FUZZY_BLOCKLIST:
                    continue
                score = fuzz.partial_ratio(alias, item_lower)
                if score >= fuzzy_threshold:
                    return idx

    return None


# ---------------------------------------------------------------------------
# Parse single response
# ---------------------------------------------------------------------------

def parse_single_response(
    response_text: str,
    brand: BrandConfig,
    scoring=None,
    fuzzy_enabled: bool = True,
    fuzzy_threshold: int = 85,
    fuzzy_partial_threshold: int = 90,
) -> BrandMention:
    """
    Parse a single LLM response for a single brand.

    Uses 3-layer detection: exact -> domain -> fuzzy.
    Returns a BrandMention with found status, rank, top-3, visibility score, and match method.
    """
    if scoring is None:
        cfg = StudyConfig.load()
        scoring = cfg.scoring

    # Multi-layer brand detection
    found, match_text, match_method, fuzzy_score = find_brand_in_text(
        response_text, brand,
        fuzzy_enabled=fuzzy_enabled,
        fuzzy_threshold=fuzzy_threshold,
        fuzzy_partial_threshold=fuzzy_partial_threshold,
    )

    # Extract ranked list and find position
    ranked_items = _extract_ranked_list(response_text)
    rank_position = _find_brand_rank(
        ranked_items, brand,
        fuzzy_enabled=fuzzy_enabled,
        fuzzy_threshold=fuzzy_threshold,
    ) if ranked_items else None

    # If found in text but not in a list, set rank to N+1 (mentioned but unranked)
    if found and rank_position is None and ranked_items:
        rank_position = len(ranked_items) + 1

    in_top3 = rank_position is not None and rank_position <= 3
    vis_score = scoring.score(rank_position) if found else 0

    return BrandMention(
        brand_name=brand.name,
        found=found,
        rank_position=rank_position,
        in_top3=in_top3,
        visibility_score=vis_score,
        match_text=match_text,
        match_method=match_method,
        fuzzy_score=fuzzy_score,
    )


# ---------------------------------------------------------------------------
# Batch parsing
# ---------------------------------------------------------------------------

def parse_all_responses(raw_df: pd.DataFrame, fuzzy_enabled: bool = True) -> pd.DataFrame:
    """
    Parse all raw responses and produce the analysis-ready dataset.

    Input: DataFrame with columns [prompt_id, prompt_text, cluster, model, run_id, response, ...]
    Output: DataFrame with one row per (prompt, model, run, brand) with all metrics.
    """
    cfg = StudyConfig.load()
    brands = cfg.brands
    scoring = cfg.scoring

    records = []
    total = len(raw_df) * len(brands)
    logger.info(f"Parsing {len(raw_df)} responses x {len(brands)} brands = {total} evaluations")
    logger.info(f"Fuzzy matching: {'enabled' if fuzzy_enabled else 'disabled'}")

    for _, row in raw_df.iterrows():
        error_val = row.get("error")
        if pd.notna(error_val) and error_val:
            continue

        response_text = str(row.get("response", ""))
        if not response_text or response_text == "nan":
            continue

        for brand in brands:
            mention = parse_single_response(
                response_text, brand, scoring,
                fuzzy_enabled=fuzzy_enabled,
            )

            records.append({
                "prompt_id": row["prompt_id"],
                "prompt_text": row["prompt_text"],
                "cluster": row["cluster"],
                "model": row["model"],
                "model_id": row.get("model_id", ""),
                "run_id": row["run_id"],
                "temperature": row.get("temperature", 0.7),
                "brand": mention.brand_name,
                "brand_found": int(mention.found),
                "rank_position": mention.rank_position if mention.rank_position else 999,
                "top3": int(mention.in_top3),
                "visibility_score": mention.visibility_score,
                "match_text": mention.match_text,
                "match_method": mention.match_method,
                "fuzzy_score": mention.fuzzy_score,
                "timestamp": row.get("timestamp", ""),
            })

    df = pd.DataFrame(records)
    logger.info(f"Parsing complete: {len(df)} evaluation records")

    # Log detection method breakdown
    if not df.empty:
        found_df = df[df["brand_found"] == 1]
        if not found_df.empty:
            method_counts = found_df["match_method"].value_counts()
            logger.info(f"Detection methods: {dict(method_counts)}")

    return df


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Parse raw LLM responses into structured metrics")
    parser.add_argument("--input", type=str, default="data/raw_responses.csv", help="Raw response file")
    parser.add_argument("--output", type=str, default="data/parsed_metrics.csv", help="Output metrics file")
    parser.add_argument("--no-fuzzy", action="store_true", help="Disable fuzzy matching")
    args = parser.parse_args()

    from src.utils import load_raw_data
    raw_df = load_raw_data(args.input)
    metrics_df = parse_all_responses(raw_df, fuzzy_enabled=not args.no_fuzzy)
    metrics_df.to_csv(args.output, index=False, encoding="utf-8")
    logger.info(f"Saved parsed metrics to {args.output}")


if __name__ == "__main__":
    main()
