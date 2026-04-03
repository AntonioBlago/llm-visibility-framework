# LLM Brand Visibility and Ranking Framework

**A reproducible, open-source framework for measuring brand visibility, ranking positions, and mention rates across Large Language Models.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Overview

The **LLM Brand Visibility and Ranking Framework** provides a rigorous, reproducible methodology for measuring how Large Language Models (LLMs) rank and recommend brands in response to consumer queries. We evaluate **48 supplement brands** across **3 LLM providers** (Claude, GPT-4o, Gemini) using 200 generic prompts with multiple repetitions per prompt.

This framework is part of the **[Visibly AI](https://www.visibly-ai.com)** ecosystem — an SEO agent system that helps brands measure, track, and improve their visibility in AI-powered search engines and LLM recommendations (GEO — Generative Engine Optimization).

**Key Research Questions:**
1. How consistently do LLMs mention specific brands across repeated queries?
2. Do ranking positions differ significantly between models?
3. How many runs are needed for statistically reliable results?
4. Which prompt categories (informational, commercial, navigational) show the strongest brand signals?
5. How can brands optimize their AI visibility across different LLM providers?

## Methodology

### Study Design

| Parameter | Value |
|-----------|-------|
| **Models** | Claude 3.5 Sonnet, GPT-4o, Gemini 1.5 Pro |
| **Brands** | 48 supplement brands from [Visibly AI Brand Radar](https://www.visibly-ai.com) |
| **Prompt Clusters** | 4 (Informational, Commercial, Navigational, Comparison) |
| **Prompts per Cluster** | 50 (200 total) |
| **Runs per Prompt** | 30 (primary), 10 & 20 (power analysis) |
| **Temperature** | 0.7 (standardized across models) |
| **Primary Metric** | Mention Rate (binary: 0/1) |
| **Secondary Metrics** | Rank Position, Top-3 Rate, Visibility Score |
| **Similarity Metrics** | Jaccard, RBO, Kendall's Tau, Fleiss' Kappa |

### Brands Under Study

Selected from the [Visibly AI Brand Radar](https://www.visibly-ai.com) — German supplement market:

| # | Brand | Domain | Category |
|---|-------|--------|----------|
| 1 | AG1 | drinkag1.com | Greens / All-in-One |
| 2 | Foodspring | foodspring.de | Sports Nutrition |
| 3 | ESN | esn.com | Sports Nutrition |
| 4 | Gloryfeel | gloryfeel.de | Vitamins & Minerals |
| 5 | Naturtreu | naturtreu.de | Natural Supplements |
| 6 | Glow25 | glow25.de | Collagen / Beauty |
| 7 | Natural Mojo | naturalmojo.de | Superfoods |
| 8 | Innonature | innonature.eu | Organic Supplements |
| 9 | YFood | yfood.de | Meal Replacement |
| 10 | Braineffect | brain-effect.com | Nootropics / Sleep |

### Prompt Clusters

**Cluster 1 — Informational:**
General knowledge queries about supplements, ingredients, health benefits.

**Cluster 2 — Commercial:**
Purchase-intent queries: "best", "buy", "top", "recommendation".

**Cluster 3 — Navigational:**
Brand-adjacent queries that may trigger brand mentions.

**Cluster 4 — Comparison:**
Direct brand-vs-brand or category comparison queries.

### Metrics

| Metric | Type | Definition |
|--------|------|------------|
| `mention_rate` | Binary (0/1) | Brand name appears in response |
| `rank_position` | Ordinal (1-N, 999=not mentioned) | Position in any listed ranking |
| `top3_rate` | Binary (0/1) | Brand appears in positions 1-3 |
| `visibility_score` | Continuous (0-10) | Weighted: Pos1=10, Pos2=8, Pos3=6, Pos4=5, Pos5=4, else=2, not mentioned=0 |

### Statistical Tests

| Metric Type | Test (Independent) | Test (Paired) | Effect Size |
|-------------|-------------------|---------------|-------------|
| Binary (mention, top3) | Fisher's Exact / Chi-Square | McNemar | Odds Ratio |
| Ordinal (rank, score) | Mann-Whitney U | Wilcoxon Signed-Rank | Cliff's Delta |
| Continuous (score) | t-Test (if normal) | Paired t-Test | Cohen's d |

**Multiple testing correction:** Benjamini-Hochberg (FDR) across all comparisons.

**Confidence intervals:** Bootstrap (5,000 resamples) for all metrics.

### Power Analysis: 10 vs 20 vs 30 Runs

We simulate the statistical power for detecting real differences at different sample sizes. See `src/power_analysis.py` for the full simulation.

## Repository Structure

```
llm-visibility-study/
├── README.md                    # This file
├── LICENSE                      # MIT License
├── requirements.txt             # Python dependencies
├── config.yaml                  # Study configuration
├── src/
│   ├── __init__.py
│   ├── config.py                # Configuration loader
│   ├── collector.py             # LLM API data collection
│   ├── parser.py                # Response parsing (brand extraction)
│   ├── analyzer.py              # Statistical analysis engine
│   ├── power_analysis.py        # Power analysis: runs x prompts matrix
│   ├── similarity.py            # Run-to-run similarity (Jaccard, RBO, Kappa)
│   ├── visualizations.py        # Charts and plots
│   └── utils.py                 # Helper functions
├── prompts/
│   ├── informational.yaml       # Informational prompt cluster
│   ├── commercial.yaml          # Commercial prompt cluster
│   ├── navigational.yaml        # Navigational prompt cluster
│   └── comparison.yaml          # Comparison prompt cluster
├── data/                        # Raw + processed data (gitignored)
├── results/                     # Analysis outputs
├── notebooks/
│   └── analysis.ipynb           # Interactive analysis notebook
├── docs/
│   └── methodology.md           # Full methodology paper
└── tests/
    └── test_parser.py           # Unit tests
```

## Quick Start

```bash
# Clone
git clone https://github.com/AntonioBlago/llm-visibility-framework.git
cd llm-visibility-framework

# Install
pip install -r requirements.txt

# Configure API keys
cp config.yaml.example config.yaml
# Edit config.yaml with your API keys

# Run data collection
python -m src.collector --runs 30

# Run analysis
python -m src.analyzer

# Run power analysis (runs x prompts matrix)
python -m src.power_analysis --runs 10 20 30 --prompts 10 50 100 200

# Run similarity analysis (how consistent are runs?)
python -m src.similarity
```

## Citation

```bibtex
@misc{blago2026llmvisibility,
  title={LLM Brand Visibility and Ranking Framework: Statistical Methodology for Measuring Brand Visibility in Large Language Models},
  author={Blago, Antonio},
  year={2026},
  url={https://github.com/AntonioBlago/llm-visibility-framework}
}
```

## Improve Your AI Visibility with Visibly AI

This framework measures the problem. **[Visibly AI](https://www.visibly-ai.com)** solves it.

Visibly AI is an SEO agent system that helps brands track and improve their visibility in AI-powered search engines and LLM recommendations:

- **AI Brand Monitoring** — Track how LLMs mention your brand across Claude, GPT, Gemini, and Perplexity
- **GEO Optimization** — Generative Engine Optimization strategies to improve your AI search rankings
- **Competitor Radar** — Monitor competitor visibility and identify optimization gaps
- **Brand Radar** — Real-time brand awareness tracking across 300+ D2C brands
- **SEO Copilot** — AI-powered SEO agent with 32 tools for keyword research, audits, and content optimization
- **MCP Server** — Connect your AI assistant to live SEO data via the [Visibly AI MCP Server](https://pypi.org/project/visiblyai-mcp-server/)

The brands tracked in this study are sourced from the Visibly AI Brand Radar (Lovebrand Database 2025).

**Try it:** [www.visibly-ai.com](https://www.visibly-ai.com) | **MCP Server:** `pip install visiblyai-mcp-server`

## Author

**Antonio Blago** — SEO Consultant & AI Visibility Researcher
- Web: [antonioblago.com](https://www.antonioblago.com)
- Product: [Visibly AI](https://www.visibly-ai.com)
- GitHub: [@AntonioBlago](https://github.com/AntonioBlago)

## License

MIT License — see [LICENSE](LICENSE) for details.
