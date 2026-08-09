# Methodology: Measuring Brand Visibility in Large Language Models

**Author:** Antonio Blago
**Date:** April 2026
**Version:** 1.0

## Abstract

This document describes a reproducible statistical methodology for measuring how Large Language Models (LLMs) mention, rank, and recommend brands in response to consumer queries. The methodology is applied to 10 supplement brands in the German market, evaluated across 3 LLM providers (Claude, GPT-4o, Gemini) using 70 generic prompts with 30 repeated runs each.

All prompts are **brand-neutral** — no brand names appear in any prompt. Brands are only detected in the model output, ensuring unbiased measurement of organic brand visibility.

---

## 1. Research Questions

1. **Mention Rate**: How often do LLMs spontaneously mention specific brands when answering generic supplement queries?
2. **Ranking Consistency**: How stable are brand rankings across repeated runs of the same prompt?
3. **Model Differences**: Do Claude, GPT-4o, and Gemini differ significantly in which brands they recommend?
4. **Prompt Sensitivity**: Do different prompt categories (informational, commercial, navigational, comparison) produce different brand visibility patterns?
5. **Sample Size Requirements**: How many runs and prompts are needed for statistically reliable results?

---

## 2. Study Design

### 2.1 Independent Variables

| Variable | Levels | Type |
|----------|--------|------|
| **Model** | Claude, GPT-4o, Gemini | Between-subjects |
| **Prompt Cluster** | Informational, Commercial, Navigational, Comparison | Within-subjects |
| **Run** | 1-30 (per prompt per model) | Repeated measure |

### 2.2 Dependent Variables (Metrics)

| Metric | Type | Definition | Statistical Treatment |
|--------|------|------------|-----------------------|
| `mention_rate` | Binary (0/1) | Brand name appears in response | Fisher's exact, McNemar |
| `rank_position` | Ordinal (1-N, 999=absent) | Position in any listed ranking | Mann-Whitney U, Wilcoxon |
| `top3_rate` | Binary (0/1) | Brand in positions 1-3 | Fisher's exact |
| `visibility_score` | Ordinal (0-10) | Weighted score: Pos1=10, Pos2=8, Pos3=6, Pos4=5, Pos5=4, mentioned=2, absent=0 | Mann-Whitney U |

### 2.3 Brands Under Study

10 supplement brands selected from the Visibly AI Brand Radar (German market):

| # | Brand | Category | Selection Rationale |
|---|-------|----------|---------------------|
| 1 | AG1 | Greens / All-in-One | High brand awareness, heavy marketing spend |
| 2 | Foodspring | Sports Nutrition | Major German D2C brand |
| 3 | ESN | Sports Nutrition | Established German whey brand |
| 4 | Gloryfeel | Vitamins & Minerals | Amazon-dominant brand |
| 5 | Naturtreu | Natural Supplements | Organic/natural positioning |
| 6 | Glow25 | Collagen / Beauty | D2C collagen brand |
| 7 | Natural Mojo | Superfoods | Social media-driven brand |
| 8 | Innonature | Organic Supplements | Bio-certified supplements |
| 9 | YFood | Meal Replacement | VC-funded meal replacement |
| 10 | Braineffect | Nootropics / Sleep | Performance supplement niche |

**Selection criteria:**
- All are active in the German supplement market
- Represent different product categories
- Mix of brand awareness levels (high/medium/low)
- Mix of distribution channels (D2C, Amazon, retail)

### 2.4 Prompt Design

**Critical rule: All prompts are GENERIC. No brand names are ever mentioned in any prompt.**

Brands are only detected in the LLM's output. This ensures we measure **organic visibility** — how likely a model is to spontaneously recommend a brand without being prompted about it.

**4 Prompt Clusters:**

| Cluster | # Prompts | Intent | Example |
|---------|-----------|--------|---------|
| Informational | 20 | Knowledge-seeking | "Wie sinnvoll sind Greens Pulver als Nahrungsergaenzung?" |
| Commercial | 20 | Purchase intent | "Was ist das beste Greens Pulver in Deutschland?" |
| Navigational | 15 | Brand-adjacent | "Deutsche Startups im Bereich Nahrungsergaenzung" |
| Comparison | 15 | Category comparison | "Ranking deutscher Supplement-Marken nach Qualitaet" |

**Total: 70 prompts** (all in German, reflecting the target market).

**Prompt quality rules:**
- No leading questions
- No brand names or obvious brand references
- German language (target market)
- Natural phrasing (as a real user would ask)
- Diverse question structures

### 2.5 Prompt Sets as Measurement Instruments

The prompt set is part of the measurement instrument. A visibility score is therefore conditional on the prompt family, buyer persona, journey stage, buying context and constraint set used to observe the market, not a free-standing property of a brand.

Report every result as visibility under a defined prompt set, version, prompt family, buyer persona, journey stage, buying context, constraint set, market definition, model set and run date. A changed prompt set is a changed instrument and starts a new time series.

This matters most when comparing generic and contextual prompt families:

| Prompt family | Measures | Valid interpretation |
|---------------|----------|----------------------|
| Generic prompts | Spontaneous brand visibility under broad category framing | Organic category visibility for the defined market |
| Contextual prompts | Visibility under a specified buyer situation, such as industry, existing systems or compliance constraints | Scenario-specific visibility under a narrower market definition |
| Branded prompts | Attributes and associations when the brand is named | Perception, not organic visibility |

Differences between prompt families should not be interpreted as evidence that content, structured data, `llms.txt`, PR or other GEO actions caused a lift unless the prompt set was held constant and the intervention itself changed.

Buyer persona, funnel stage, buying context and constraint set must also stay stable in paired comparisons. A broad awareness prompt and a decision-stage prompt with budget, industry, existing tools or compliance constraints can validly produce different visibility patterns because they encode different buyer situations.

A constraint set is any explicit requirement that admits or excludes product classes, such as self-hosting, data residency, compliance requirements, budget caps, integration dependencies, company size or existing stack. If a contextual prompt admits a previously filtered-out solution class, the result is a market-definition finding, not a prompt trick and not an optimization lift.

Customer evidence is an optional but recommended input for designing better prompt instruments before measurement. Questionnaires, sales notes, CRM loss reasons, support tickets, reviews and on-site search logs can help identify real buyer wording, objections, constraints and decision criteria. Use only aggregated or anonymized evidence in prompt design, record the evidence sources with the prompt set if they were used, and never mix prompt rewrites caused by new customer data into an existing time series.

---

## 3. Data Collection Protocol

### 3.1 API Configuration

All models use identical parameters where possible:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Temperature | 0.7 | Standard creative temperature, allows variation |
| Max tokens | 2048 | Sufficient for detailed responses with lists |
| System prompt | None | No system prompt to avoid bias |
| Seed | Not set | Temperature > 0 provides natural variation |

### 3.2 Collection Procedure

For each of 70 prompts x 3 models x 30 runs = **6,300 API calls**:

1. Send prompt to model API
2. Record full response text
3. Record latency, timestamp, model version
4. Wait 1 second between calls (rate limiting)
5. Store incrementally as JSONL (crash-safe)

### 3.3 Data Schema

Each raw record contains:

```
prompt_id, prompt_text, cluster, model, model_id, provider,
temperature, run_id, response, latency_s, error, timestamp
```

---

## 4. Response Parsing

### 4.1 Brand Detection

For each response, we check whether each of the 10 brands is mentioned:

1. **Alias matching**: Each brand has 2-4 aliases (e.g., "ag1", "athletic greens", "AG1 by Athletic Greens")
2. **Word-boundary aware**: Regex with `\b` prevents false positives (e.g., "essence" matching "esn")
3. **Case-insensitive**: All matching is case-insensitive

### 4.2 Rank Extraction

LLM responses often contain numbered or bulleted lists. The parser:

1. Identifies list items (numbered, bulleted, or bold-formatted)
2. Assigns 1-based rank positions
3. Matches brands against list items
4. If brand is mentioned in text but not in a list: assigned rank = N+1 (mentioned but unranked)
5. If brand is not mentioned: rank = 999

### 4.3 Visibility Scoring

Weighted score based on rank position:

| Position | Score | Rationale |
|----------|-------|-----------|
| 1 | 10 | Top recommendation |
| 2 | 8 | Strong recommendation |
| 3 | 6 | Notable recommendation |
| 4 | 5 | Listed but not top |
| 5 | 4 | Listed but not top |
| 6+ (mentioned) | 2 | Mentioned |
| Not mentioned | 0 | Absent |

---

## 5. Statistical Analysis

### 5.1 Descriptive Statistics

For each (model, brand, cluster) combination:
- **Mention rate**: Mean + 95% bootstrap CI
- **Rank position**: Median + IQR (ordinal data, not mean)
- **Top-3 rate**: Proportion + 95% bootstrap CI
- **Visibility score**: Mean + SD + bootstrap CI

### 5.2 Hypothesis Testing

**Primary hypothesis (H1)**: Brand mention rates differ significantly between LLM providers.

**Secondary hypotheses**:
- H2: Rank positions differ between providers
- H3: Visibility scores differ between providers
- H4: Mention rates differ across prompt clusters

#### Test Selection

| Metric | Data Type | Independent Groups | Paired Groups |
|--------|-----------|-------------------|---------------|
| Mention rate | Binary | Fisher's exact test | McNemar test |
| Top-3 rate | Binary | Fisher's exact test | McNemar test |
| Rank position | Ordinal | Mann-Whitney U | Wilcoxon signed-rank |
| Visibility score | Ordinal | Mann-Whitney U | Wilcoxon signed-rank |

**Rationale for non-parametric tests:**
LLM output distributions are typically:
- Heavily skewed (many zeros for mention rate)
- Non-normal (rank positions are discrete, bounded)
- Heteroskedastic (variance differs by brand/model)

Non-parametric tests make fewer distributional assumptions and are more appropriate for this data.

### 5.3 Effect Sizes

A p-value alone does not indicate practical relevance. We report:

| Metric Type | Effect Size | Interpretation Thresholds |
|-------------|-------------|---------------------------|
| Binary | Odds Ratio | 1.0 = no effect, > 1.5 = small, > 2.5 = medium, > 4.0 = large |
| Ordinal | Cliff's Delta | < 0.147 = negligible, < 0.33 = small, < 0.474 = medium, >= 0.474 = large |
| Continuous | Cohen's d | < 0.2 = negligible, < 0.5 = small, < 0.8 = medium, >= 0.8 = large |

### 5.4 Confidence Intervals

**Bootstrap method** (5,000 resamples, percentile method):
- For point estimates (mention rate, visibility score)
- For differences between groups
- More robust than parametric CIs for skewed LLM data

### 5.5 Multiple Testing Correction

With 3 model pairs x 4 metrics x 4 clusters = 48 tests, we apply:

**Benjamini-Hochberg (FDR) correction** at alpha = 0.05.

Rationale: Bonferroni is overly conservative for correlated tests. BH controls the false discovery rate, which is more appropriate for exploratory research.

---

## 6. Power Analysis

### 6.1 Design Question

How many runs per prompt and how many prompts are needed to reliably detect brand visibility differences?

### 6.2 Monte Carlo Simulation

We simulate 10,000 iterations for each combination:

| Runs per Prompt | Prompts | Observations per Group | Total API Calls (3 models) |
|----------------|---------|----------------------|---------------------------|
| 10 | 10 | 100 | 300 |
| 10 | 50 | 500 | 1,500 |
| 10 | 100 | 1,000 | 3,000 |
| 10 | 200 | 2,000 | 6,000 |
| 20 | 10 | 200 | 600 |
| 20 | 50 | 1,000 | 3,000 |
| 20 | 100 | 2,000 | 6,000 |
| 20 | 200 | 4,000 | 12,000 |
| 30 | 10 | 300 | 900 |
| 30 | 50 | 1,500 | 4,500 |
| 30 | 100 | 3,000 | 9,000 |
| 30 | 200 | 6,000 | 18,000 |

### 6.3 Effect Size Scenarios

**Mention Rate (binary):**
- Tiny: 3 percentage points (0.50 vs 0.53)
- Small: 5pp (0.30 vs 0.35)
- Medium: 15pp (0.30 vs 0.45)
- Large: 25pp (0.30 vs 0.55)

**Rank Position (ordinal):**
- Small, medium, large shifts in log-normal rank distributions

**Visibility Score (continuous):**
- 0.5pt, 1.5pt, 3.0pt differences on 0-10 scale

### 6.4 Recommendations

| Design | Power for Medium Effect | Power for Small Effect | Cost |
|--------|------------------------|----------------------|------|
| 10 runs x 10 prompts | ~30% | ~10% | 300 calls |
| 20 runs x 50 prompts | ~75% | ~25% | 3,000 calls |
| **30 runs x 50 prompts** | **~85%** | **~35%** | **4,500 calls** |
| 30 runs x 100 prompts | ~95% | ~55% | 9,000 calls |
| 30 runs x 200 prompts | ~99% | ~80% | 18,000 calls |

**Recommended minimum**: 30 runs x 50 prompts (4,500 API calls total).
**Recommended for publication**: 30 runs x 100 prompts (9,000 API calls total).

---

## 7. Interpretation Guidelines

### 7.1 What Constitutes a Meaningful Result?

A result is considered meaningful only if ALL three conditions are met:

1. **Statistically significant** after FDR correction (p_corrected < 0.05)
2. **Practically relevant** effect size (Cliff's Delta >= 0.147 or Odds Ratio >= 1.5)
3. **Consistent** across at least 2 of 4 prompt clusters

### 7.2 Known Limitations

1. **Temporal instability**: LLM outputs change with model updates. Results are snapshots, not permanent truths.
2. **Temperature variation**: Even at temperature=0, some models show non-deterministic behavior.
3. **Cultural/linguistic bias**: German prompts may favor German brands in some models.
4. **Training data recency**: Models may not know recently launched brands.
5. **Prompt sensitivity**: Results may change with paraphrased prompts (robustness not tested in v1.0).

### 7.3 What This Study Does NOT Measure

- Accuracy of brand recommendations (whether the model is "right")
- User satisfaction with recommendations
- Causal factors behind brand visibility (training data composition, RLHF, etc.)
- Real-world purchase behavior impact

---

## 8. Reproducibility

All code, prompts, and analysis scripts are available at:
`https://github.com/AntonioBlago/llm-visibility-study`

To reproduce:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set API keys
export ANTHROPIC_API_KEY="..."
export OPENAI_API_KEY="..."
export GOOGLE_API_KEY="..."

# 3. Collect data
python -m src.collector --runs 30

# 4. Parse responses
python -m src.parser

# 5. Run analysis
python -m src.analyzer

# 6. Run power analysis
python -m src.power_analysis --runs 10 20 30 --prompts 10 50 100 200

# 7. Generate figures
python -m src.visualizations
```

**Random seed**: 42 (used consistently for bootstrap and simulations).

---

## References

1. Cliff, N. (1993). Dominance statistics: Ordinal analyses to answer ordinal questions. *Psychological Bulletin*, 114(3), 494-509.
2. Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate. *Journal of the Royal Statistical Society*, 57(1), 289-300.
3. Efron, B., & Tibshirani, R. (1994). *An Introduction to the Bootstrap*. Chapman and Hall/CRC.
4. Romano, J., Kromrey, J., Coraggio, J., & Skowronek, J. (2006). Appropriate statistics for ordinal level data. *Journal of Modern Applied Statistical Methods*, 5(1).
