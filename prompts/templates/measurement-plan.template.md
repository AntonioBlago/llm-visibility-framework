# Measurement Plan Template — Baseline, Variance Runs, Monthly Set

Use this template to document *what runs when, with which context, and how it is reported* before the first run. It complements the prompt set itself: the prompt set says what is asked, the measurement plan says how the answers become comparable numbers. See [Phase 4.4 of the framework](../../docs/prompt-framework.md#44-run-design-for-tool-based-monitoring).

Fill in the counts from your prompt set (`N_core`, `N_control`, …) and keep this file versioned next to the prompt set (`v1.0`, `v1.1`, …).

## 1. Measurement groups

| Group | Prompts | Brand in prompt | Context | Systems | First month (baseline) | Afterwards | Reported as |
|-------|---------|-----------------|---------|---------|------------------------|------------|-------------|
| Core, generic | `N_core_generic` | no | persona context sentence | fixed systems | run 1 with all prompts, then runs 2 and 3 of the monthly set | monthly; frozen from run `<freeze run>` | mention rate and citation rate per topic, persona and system; baseline value only after the three first-month runs, with spread |
| Core, feature | `N_core_feature` | no (but names brand attributes) | persona | fixed systems | as core | monthly | **separately**: recognition via attributes (e.g. vegan, made in `<country>`, handmade, refill); feature prompts inflate the mention rate, never merge them into the generic rate |
| Core, seasonal | `N_core_seasonal` | no | persona | fixed systems | as core | monthly inside the season window | **separately** in the monthly quota, so the season does not distort the year-over-year comparison |
| Classification control | `N_control` | no | **none** | fixed systems | as core (three runs) | monthly | classification correct / vague / wrong; not part of the mention rate |
| Brand sentiment (Type B) | `N_brand` | yes | none | fixed systems | once | on demand (e.g. after an About-page relaunch) | **single measurement, not a baseline**: sentiment, factual errors (retailer, category, claims), cited sources |
| Benchmark brands | `N_benchmark` | yes (competitor) | none | fixed systems | once | on demand | single measurement on the same scale |
| Reserve | `N_reserve` | no | none | fixed systems | once | only after promotion into the monthly set (until the freeze run) | single measurement; shows gaps from which the monthly set is completed |
| Service questions | `N_service` | no | persona | fixed systems | after validation with customer service | monthly, like core | like core |
| AI Overviews | `N_head_terms` head terms | — | — | Google SERP pull, target country | once | monthly | **separately**: is there an AI answer, and is the brand in it |

Rules:

- Fixed systems are named in the plan (e.g. "ChatGPT with web search, Gemini"); optional systems (e.g. Perplexity) are marked optional and increase the call budget accordingly.
- The baseline run counts as run 1 of the monthly set. Runs 2 and 3 in the first month measure the spread; report the spread (min–max) next to every core value before you set targets.
- From the freeze run on, the set does not change. Additions from the reserve are allowed until then and are appended with new IDs; existing IDs are never renumbered.
- Single measurements (brand, benchmark, reserve) are momentary readings, not baselines. Do not compare them month over month unless the group was re-run in full.

## 2. Call budget

```
first month  = (N_all + 2 × N_monthly) × fixed_systems
afterwards   =  N_monthly × fixed_systems           per month
optional     = + N_monthly × optional_systems        per month
```

where `N_all` = every prompt of every group once, `N_monthly` = core + classification control (+ service after validation).

## 3. Per-run documentation (one row per prompt and system)

| Field | Content |
|-------|---------|
| Run date | ISO date |
| System and model version | e.g. `ChatGPT, GPT-5.x, web search on`, `Gemini 2.x` |
| Web search | on / off |
| Country, language | e.g. DE, de |
| Prompt ID, group, evaluation tag | `generic` / `feature` / `seasonal` / `control` / `brand` / `benchmark` / `reserve` / `service` |
| Persona and context sentence | verbatim, or `none` for control groups |
| Prompt text | verbatim |
| Full answer | stored, not summarized |
| Brand mentioned | yes / no; position if listed |
| Classification | correct / vague / wrong (control group) |
| Context | positive / neutral / critical |
| Top-3 competitors named | from the competitor roster (all roster brands count; the product-field mapping only attributes them to topics) |
| Cited sources | domains, marked as brand site / retailer / magazine / other |

## 4. Reporting rules

1. Per topic and per persona first; totals second.
2. Totals both ways: **demand-weighted** (topics with more prompts weigh more) and **equal-weighted per topic**. State which one is the headline number.
3. Generic, feature and seasonal rates are three numbers, never one.
4. Targets are set after the third first-month run, with the spread known; they are targets, not forecasts.
5. Every report carries the metadata from [Phase 5.4](../../docs/prompt-framework.md#54-required-report-metadata): prompt set version, persona shares, evaluation-tag composition, weighting, systems, run dates, spread.
