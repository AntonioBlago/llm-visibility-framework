# LLM Brand Visibility and Ranking Framework

**A reproducible, open-source framework for measuring brand visibility, ranking positions, and mention rates across Large Language Models.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Blog Post](https://img.shields.io/badge/Blog-Read%20the%20Study-f97316)](https://www.antonioblago.com/blog/how-llms-rank-brands-a-statistical-study-of-ai-visibility-across-claude-gpt-4o-and-gemini)

## Overview

The **LLM Brand Visibility and Ranking Framework** measures how Large Language Models (Claude, GPT-4o, Gemini) rank and recommend brands in response to consumer queries — and gives you a repeatable workflow to track **your own brand**: analyze the business, build a versioned 50–100 prompt set, measure across models, audit, optimize.

Prompt sets are treated as measurement instruments: a visibility score is conditional on the prompt family, prompt-set version, buyer persona, journey stage, buying context, constraint set, market definition, model set and run date used to observe it. Changed prompts start a new time series; they should not be interpreted as optimization effects unless the prompt set stayed fixed and the measured intervention changed.

The methodology is validated by [a statistical study](#the-study-empirical-foundation) of 48 supplement brands × 200 prompts × 3 models with up to 30 runs per prompt. The study answers the calibration questions behind your own measurement — how many runs you need, how stable rankings are, which metrics discriminate — and its results are the defaults baked into the framework.

This framework is part of the **[Visibly AI](https://www.visibly-ai.com)** ecosystem — an SEO agent system that helps brands measure, track, and improve their visibility in AI-powered search engines and LLM recommendations (GEO — Generative Engine Optimization).

## Prompt Framework: From Business Analysis to AI Visibility Audit

Want to apply this methodology to **your own brand**? The repository includes a complete, reusable prompt framework — [docs/prompt-framework.md](docs/prompt-framework.md) — covering the full workflow:

1. **Business Analysis** — context capture, website research, customer evidence, 5–10 competitor analysis
2. **Category & Journey Mapping** — 3–7 monitoring categories, journey stages incl. the five Neuro-SEO funnel stages, prompt allocation by demand share, generic (~60%) vs. branded (~40%) prompt split
3. **Prompt Development** — build a versioned set of 50–100 prompts (W-question rules, evidence-weighted personas as context sentences, measurement groups with evaluation tags, target page per prompt)
4. **Measurement** — run the set through this repo's pipeline (collector → parser → analyzer), or in a tracking tool with the baseline / variance-run / monthly design and per-run documentation
5. **Audit** — visibility audit (mention rate, rank, share of voice) + perception audit (attributes, sentiment, USP match)
6. **Optimize & Re-measure** — GEO actions, tracking cadence, prompt-set versioning

Ready-to-use assets in [prompts/templates/](prompts/templates/): German system prompts for Custom GPTs (simple + advanced workflow), instrumented tracking-prompt templates (DE/EN), a pipeline-ready YAML cluster template, a measurement-plan template (groups, runs, call budget), and a motive-color example set.

**Framework v1.1 (September 2026)** adds what a production prompt set for a D2C brand taught us (no client data in the repo): personas weighted by the measured customer base and applied as fixed context sentences; measurement groups with evaluation tags (generic / feature / seasonal / control / brand / benchmark / reserve), because attribute prompts inflate the mention rate; a run design with a baseline and two variance runs before the first baseline value; a competitor roster merged from client and analysis lists with product fields per brand and a hard rule against retailers as benchmarks; and prompt allocation by demand share with totals reported both demand-weighted and equal-weighted. Details in [docs/prompt-framework.md](docs/prompt-framework.md) (1.5, 2.2, 2.4, 3.3, 3.7, 3.8, 4.4).

**Claude Code users:** the repo ships a skill that executes the framework step by step — run `/prompt-framework analyze <brand> <website>`, then `categories`, `develop`, `measure`, `audit` (or `full` for the guided end-to-end flow). See [.claude/skills/prompt-framework/SKILL.md](.claude/skills/prompt-framework/SKILL.md). Copy-paste commands for both the skill and the manual route are in [Quick Start — Path A](#path-a--track-your-own-brand-prompt-framework) below.

The framework builds on the [Neuro-SEO System®](https://www.antonioblago.com/de/neuro-seo-system/) (business-first analysis, sales-psychology layer) and was applied in production in the [PURELEI E-commerce GEO case study](https://www.antonioblago.com/blog/e-commerce-geo-case-study-with-purelei) — 117 prompts across ChatGPT, Perplexity, Claude, Gemini and Google AI Overviews with UTM-based revenue attribution.

## Quick Start

### Setup (both paths)

```bash
# Clone
git clone https://github.com/AntonioBlago/llm-visibility-framework.git
cd llm-visibility-framework

# Install
pip install -r requirements.txt

# Configure API keys
cp config.yaml.example config.yaml
# Edit config.yaml: set api_key_env names and export the keys
# (ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY)
```

### Path A — Track your own brand (Prompt Framework)

Follow the 6-phase [Prompt Framework](docs/prompt-framework.md): analyze the business, map categories, build a 50–100 prompt set, measure, audit.

**With Claude Code** (the skill ships with this repo — open the repo and run):

```
/prompt-framework analyze <brand> <website>   # Phase 1: business + competitor analysis
/prompt-framework categories                  # Phase 2: pick 3-7 monitoring categories
/prompt-framework develop 60                  # Phase 3: generate the prompt set (50-100)
/prompt-framework measure 30                  # Phase 4: configure + collect + analyze
/prompt-framework audit                       # Phase 5: visibility + perception audit
```

Or `/prompt-framework full <brand> <website>` for the guided end-to-end flow. Work products are stored in `data/framework/<brand>/` (gitignored).

**Without Claude Code:**

1. Work through Phases 1–2 of [docs/prompt-framework.md](docs/prompt-framework.md) manually, or paste [prompts/templates/system-prompt-simple.de.md](prompts/templates/system-prompt-simple.de.md) into a Custom GPT / Claude Project to generate the prompt table interactively.
2. Copy [prompts/templates/prompt-set.template.yaml](prompts/templates/prompt-set.template.yaml) to `prompts/<category>.yaml` per category and fill in the **generic (Type A)** prompts.
3. Add your brand and its competitors (with `aliases`) to `config.yaml → brands`, and register your clusters under `prompt_clusters`.
4. Measure: `python -m src.collector --runs 30 && python -m src.analyzer`
5. Audit the results following [Phase 5 of the framework](docs/prompt-framework.md#phase-5--audit); track branded (Type B) prompts separately with [prompts/templates/tracking-prompts.md](prompts/templates/tracking-prompts.md).

### Path B — Reproduce the study

Runs the original setup — 48 supplement brands × 200 prompts × 3 models (see [The Study](#the-study-empirical-foundation) below):

```bash
# 1. Data collection (30 runs per prompt; start with --runs 10 to test)
python -m src.collector --runs 30

# 2. Statistical analysis (mention rates, ranks, significance tests)
python -m src.analyzer

# 3. Power analysis: how many runs/prompts do you actually need?
python -m src.power_analysis --runs 10 20 30 --prompts 10 50 100 200

# 4. Run-to-run consistency (Jaccard, RBO, Fleiss' Kappa)
python -m src.similarity
```

Results land in `results/`, raw responses in `data/`.

## Repository Structure

```
llm-visibility-framework/
├── README.md                    # This file
├── .claude/
│   └── skills/
│       └── prompt-framework/    # Claude Code skill: run the framework steps
│           └── SKILL.md
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
│   ├── comparison.yaml          # Comparison prompt cluster
│   └── templates/               # Prompt framework templates
│       ├── README.md            # Template index
│       ├── system-prompt-simple.de.md    # Custom GPT system prompt (simple)
│       ├── system-prompt-advanced.de.md  # Custom GPT system prompt (full workflow)
│       ├── tracking-prompts.md  # Instrumented tracking prompts (DE/EN)
│       ├── prompt-set.template.yaml      # Pipeline-ready cluster template
│       ├── measurement-plan.template.md  # Groups, baseline/variance runs, call budget
│       └── example-motive-color-prompts.de.md  # Motive-color example set
├── data/                        # Raw + processed data (gitignored)
├── results/                     # Analysis outputs
├── notebooks/
│   └── analysis.ipynb           # Interactive analysis notebook
├── docs/
│   ├── methodology.md           # Full methodology paper
│   └── prompt-framework.md      # Brand prompt framework (analysis → audit)
└── tests/
    └── test_parser.py           # Unit tests
```

## The Study (Empirical Foundation)

The framework's defaults — 30 runs per prompt, the 50–100 prompt sizing, the metrics and the statistical tests — are not arbitrary: they come from a statistical study of the German supplement market. Use it as the calibration baseline for your own measurement. The full write-up lives in [docs/methodology.md](docs/methodology.md) and the [blog articles](#blog-article).

**Key Research Questions:**
1. How consistently do LLMs mention specific brands across repeated queries?
2. Do ranking positions differ significantly between models?
3. How many runs are needed for statistically reliable results?
4. Which prompt categories (informational, commercial, navigational) show the strongest brand signals?
5. How can brands optimize their AI visibility across different LLM providers?

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

## Blog Article

Read the full study write-up with key findings and GEO implications:

- **EN:** [How LLMs Rank Brands: A Statistical Study of AI Visibility Across Claude, GPT-4o, and Gemini](https://www.antonioblago.com/blog/how-llms-rank-brands-a-statistical-study-of-ai-visibility-across-claude-gpt-4o-and-gemini)
- **DE:** [Wie LLMs Marken ranken: Eine statistische Studie zur KI-Sichtbarkeit](https://www.antonioblago.com/de/blog/wie-llms-marken-ranken-eine-statistische-studie-zur-ki-sichtbarkeit-mit-claude-gpt-4o-und-gemini)
- **Case Study (EN):** [E-commerce GEO case study with PURELEI](https://www.antonioblago.com/blog/e-commerce-geo-case-study-with-purelei)
- **Case Study (DE):** [E-Commerce GEO Case Study: PURELEI und generative Sichtbarkeit](https://www.antonioblago.com/de/blog/e-commerce-geo-case-study-von-purelei)
- **Methodik-Hintergrund (DE):** [Neuro-SEO System®](https://www.antonioblago.com/de/neuro-seo-system/)

## Author

**Antonio Blago** — SEO Consultant & AI Visibility Researcher
- Web: [antonioblago.com](https://www.antonioblago.com)
- Product: [Visibly AI](https://www.visibly-ai.com)
- GitHub: [@AntonioBlago](https://github.com/AntonioBlago)

## License

MIT License — see [LICENSE](LICENSE) for details.
