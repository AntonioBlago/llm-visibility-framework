# Prompt Templates

Ready-to-use assets for the [Brand Prompt Framework](../../docs/prompt-framework.md) — from business analysis to a measurable 50–100 prompt set.

| File | Language | Purpose |
|------|----------|---------|
| [`system-prompt-simple.de.md`](system-prompt-simple.de.md) | DE | Lightweight system prompt for a Custom GPT / Claude Project: website research → category selection → prompt table → CSV |
| [`system-prompt-advanced.de.md`](system-prompt-advanced.de.md) | DE | Full workflow system prompt: context capture (8 fields), competitor agent mode, motive colors, funnel stages, tracking prompts, CSV export |
| [`tracking-prompts.md`](tracking-prompts.md) | DE + EN | Instrumented tracking-prompt templates with `[BRAND-n]` / `[ATTR-*]` markers for tool-based monitoring |
| [`prompt-set.template.yaml`](prompt-set.template.yaml) | — | Pipeline-ready cluster template for this repo (`prompts/<cluster>.yaml`) |
| [`example-motive-color-prompts.de.md`](example-motive-color-prompts.de.md) | DE | 30 emotionally framed prompt variants (motive colors, PURELEI example) |

## Which template do I need?

- **Generate a prompt set interactively** (workshop, client kickoff): paste `system-prompt-simple.de.md` into a Custom GPT — it walks through website research, category selection, and outputs a prompt table.
- **Full monitoring setup** (competitor set, funnel tagging, tool export): use `system-prompt-advanced.de.md`.
- **Run prompts through this repo's pipeline**: copy `prompt-set.template.yaml` to `prompts/<cluster>.yaml`, fill it, register the cluster in `config.yaml`.
- **Track manually or with external tools** (Visibly AI, Peec, Otterly, spreadsheets): wrap questions in the templates from `tracking-prompts.md`.

> Note: This folder is **not** loaded by the pipeline. `src/config.py` only reads `prompts/<cluster>.yaml` for clusters listed in `config.yaml → prompt_clusters`.
