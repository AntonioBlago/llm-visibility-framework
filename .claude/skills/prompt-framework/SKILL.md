---
name: prompt-framework
description: Run the Brand Prompt Framework step by step — analyze a business, map categories, develop a 50-100 prompt set, measure with the pipeline, and produce a visibility audit. Use when the user wants to set up or run LLM brand visibility tracking for a brand (e.g. "/prompt-framework analyze PURELEI https://purelei.com").
argument-hint: [analyze|categories|develop|measure|audit|full] [brand] [website-url]
---

# Brand Prompt Framework — Executable Steps

You are executing the [Brand Prompt Framework](../../../docs/prompt-framework.md). The first argument selects the step; remaining arguments are inputs for that step. With no arguments, ask which step to run and show the step overview below.

Work products for each brand live in `data/framework/<brand-slug>/` (gitignored — safe for client data). Every step reads the outputs of previous steps from there, so steps can run in separate sessions.

| Step | Framework phase | Output |
|------|----------------|--------|
| `analyze <brand> <url>` | 1 — Business Analysis | `business-analysis.md` |
| `categories` | 2 — Category & Journey Mapping | `categories.md` |
| `develop [total]` | 3 — Prompt Development | `prompts/<cluster>.yaml` files + `prompt-set.csv` |
| `measure [runs]` | 4 — Measurement | collector/analyzer runs |
| `audit` | 5 — Audit | `audit-report.md` |
| `full <brand> <url>` | 1→5 | all of the above |

General rules:
- Follow the phase definitions in `docs/prompt-framework.md` exactly; this file only operationalizes them.
- Ask the user for confirmation between steps when running `full`.
- Never overwrite an existing prompt set that has already been measured (prompt sets are frozen per time series — version instead: `v1.1`).

## Step: analyze

Phase 1 — Business Analysis. Requires brand name and website URL (ask if missing).

1. Fetch the website (WebFetch: homepage, then About/company page and 1-2 category pages if discoverable) and fill the context table: Brand, Industry, Products, Audience, Perspective, User problem, Market/region, USP.
2. Competitor analysis: web-search using the query patterns from framework 1.3 (`"[industry] brands [market]"`, `"[brand] alternatives"`, `"best [product category] brands"`). Identify 5-10 competitors; for each capture: website, type (direct/indirect), positioning, hero products, USP, audience.
3. Summarize shared themes across competitors and differentiation potential.
4. Write everything to `data/framework/<brand-slug>/business-analysis.md` and show the user the two tables (context + competitors). Ask the user to confirm or correct before they proceed to `categories`.

## Step: categories

Phase 2 — Category & Journey Mapping. Requires `business-analysis.md` (if missing, tell the user to run `analyze` first).

1. Propose 3-7 monitoring categories derived from the business analysis (candidates: sustainability, product quality, price/value, design & style, service, innovation, use cases, gifts & occasions).
2. For each category, note which journey stages matter (Awareness/Consideration/Decision/Retention/Advocacy) and a target prompt count.
3. Plan the split: ~60% Type A (generic, no brand name) / ~40% Type B (branded).
4. Let the user select/adjust categories, then write `data/framework/<brand-slug>/categories.md` with the agreed plan.

## Step: develop

Phase 3 — Prompt Development. Requires `categories.md`. Optional argument: total prompt count (default 60, range 50-100).

1. Generate prompts per category following framework 3.2: W-questions or natural buyer queries, user perspective (first person), one aspect per prompt, no yes/no or leading questions, target-market language, consistent persona (framework 3.3).
2. Type A prompts must not contain any brand name. Type B prompts name the brand and target attributes/USP.
3. Write pipeline files using [prompts/templates/prompt-set.template.yaml](../../../prompts/templates/prompt-set.template.yaml):
   - One `prompts/<category>.yaml` per category containing **Type A prompts only** (these feed the mention-rate pipeline).
   - Type B prompts go into separate `prompts/<category>_brand.yaml` files that are NOT registered as pipeline clusters — they are for perception tracking (framework 5.2) via tools or manual runs.
   - IDs: `<prefix>_a_01`, `<prefix>_b_01`; include `type` and `journey` metadata fields.
4. Also export `data/framework/<brand-slug>/prompt-set.csv` with columns `ID;Keyword;Themencluster;Fragetyp;W-Frage;Funnel_Stufe;Messziel;Tracking_Prompt` (tracking prompts from [prompts/templates/tracking-prompts.md](../../../prompts/templates/tracking-prompts.md)).
5. Show the user a summary table (category x type x journey counts) and the file list. Tag the set `v1.0` in the CSV header comment.

## Step: measure

Phase 4 — Measurement. Requires the Type A cluster YAML files. Optional argument: runs (default 30; 10-20 acceptable for directional monitoring).

1. Update `config.yaml`: add the brand and all competitors from `business-analysis.md` under `brands` (with `aliases` covering spelling variants), and register the Type A clusters under `prompt_clusters`. Show the diff to the user before writing.
2. Estimate cost first: `python -m src.cost_calculator` (if available) — report the estimate and get explicit user confirmation before collecting; API runs cost real money.
3. Run:
   ```bash
   python -m src.collector --runs <N>
   python -m src.analyzer
   python -m src.similarity
   ```
4. Report where results landed and any collection errors verbatim.

## Step: audit

Phase 5 — Audit. Requires completed analyzer output in `results/`.

1. Read the analyzer/similarity outputs.
2. Build the **visibility audit** (framework 5.1): mention rate per model and cluster, median rank, top-3 rate, visibility score, share of voice vs. the tracked competitors, gaps (categories/journey stages with zero or weak mentions), run-to-run stability.
3. If Type B responses exist (from tool-based or manual runs), build the **perception audit** (framework 5.2): attribute list, sentiment ratio, USP match % against the USPs in `business-analysis.md`, missing attributes.
4. Write `data/framework/<brand-slug>/audit-report.md` with a scorecard and a prioritized findings table mapped to GEO levers (framework Phase 6 table).
5. Close with re-measurement guidance: frozen prompt set version, cadence (monthly/quarterly), paired tests for before-after comparisons (McNemar/Wilcoxon — see `docs/methodology.md`).

## Step: full

Run analyze → categories → develop → measure → audit in order, pausing for user confirmation after each step (category selection and cost approval are mandatory stops).
