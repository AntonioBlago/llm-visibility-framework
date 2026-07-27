# Instrumented Tracking-Prompt Templates

Templates that wrap a W-question in a fixed answer frame with **machine-readable markers** — for monitoring without a response parser (spreadsheets) or with external tools (Visibly AI, Peec, Otterly, Sistrix).

> **When NOT to use these:** This repo's pipeline sends *naked prompts* and extracts brands with [`src/parser.py`](../../src/parser.py). Instrumented prompts change model behavior (they explicitly ask for brand names), so results are **not comparable** with naked-prompt measurements. Pick one variant per time series and stay with it — see [Phase 3.4 of the framework](../../docs/prompt-framework.md#34-naked-vs-instrumented-prompts).

**Marker scheme:**

| Marker | Meaning |
|--------|---------|
| `[BRAND-1]`, `[BRAND-2]`, … | Brand names in order of mention (Type A) |
| `[ATTR-POS]` | Positive attribute (Type B) |
| `[ATTR-NEU]` | Neutral attribute (Type B) |
| `[ATTR-NEG]` | Negative attribute (Type B) |

---

## Type A — Generic question (measures brand mention + position)

### German

```
Beantworte die folgende Frage sachlich und strukturiert.

Kontext:
- Branche: {{BRANCHE}}
- Zielgruppe: {{ZIELGRUPPE}}
- Perspektive: {{PERSPEKTIVE}}
- Markt: {{MARKT}}

Regeln:
- Maximal 120 Wörter
- Neutrale, erklärende Sprache
- WICHTIG: Nenne konkrete, echte Markennamen. Setze vor jeden Markennamen einen Marker in der Reihenfolge der Nennung: [BRAND-1] Markenname, [BRAND-2] Markenname, usw.
- Beispiel: "Bekannte Anbieter sind [BRAND-1] Mejuri, [BRAND-2] PURELEI und [BRAND-3] Ana Luisa."
- Keine Rückfragen stellen
- Keine Kaufempfehlungen

Struktur:
1. Kurze Einordnung
2. Relevante Aspekte
3. Konkrete Markenbeispiele mit Markern

Frage:
{{W_FRAGE}}
```

### English

```
Answer the following question factually and in a structured way.

Context:
- Industry: {{INDUSTRY}}
- Audience: {{AUDIENCE}}
- Perspective: {{PERSPECTIVE}}
- Market: {{MARKET}}

Rules:
- Maximum 120 words
- Neutral, explanatory language
- IMPORTANT: Name concrete, real brand names. Put a marker before each brand name in order of mention: [BRAND-1] Brand name, [BRAND-2] Brand name, etc.
- Example: "Well-known providers include [BRAND-1] Mejuri, [BRAND-2] PURELEI and [BRAND-3] Ana Luisa."
- Do not ask follow-up questions
- No purchase recommendations

Structure:
1. Brief context
2. Relevant aspects
3. Concrete brand examples with markers

Question:
{{QUESTION}}
```

**Evaluation (Type A):** mentioned yes/no · position of `[BRAND-n]` marker · surrounding context · which competitors appear alongside.

---

## Type B — Branded question (measures attributes + sentiment)

### German

```
Beantworte die folgende Frage sachlich und strukturiert.

Kontext:
- Branche: {{BRANCHE}}
- Zielgruppe: {{ZIELGRUPPE}}
- Perspektive: {{PERSPEKTIVE}}
- Markt: {{MARKT}}

Regeln:
- Maximal 120 Wörter
- Neutrale, erklärende Sprache
- WICHTIG: Kennzeichne jede genannte Eigenschaft oder jedes Attribut mit einem Marker:
  - [ATTR-POS] vor positiven Eigenschaften
  - [ATTR-NEU] vor neutralen Eigenschaften
  - [ATTR-NEG] vor negativen Eigenschaften
- Beispiel: "PURELEI ist bekannt für [ATTR-POS] nachhaltiges Gold, [ATTR-POS] Hawaii-inspirierte Designs und [ATTR-NEU] Influencer-Marketing."
- Keine Rückfragen stellen
- Keine Kaufempfehlungen

Struktur:
1. Kurze Einordnung
2. Eigenschaften mit Markern
3. Besonderheiten

Frage:
{{W_FRAGE}}
```

### English

```
Answer the following question factually and in a structured way.

Context:
- Industry: {{INDUSTRY}}
- Audience: {{AUDIENCE}}
- Perspective: {{PERSPECTIVE}}
- Market: {{MARKET}}

Rules:
- Maximum 120 words
- Neutral, explanatory language
- IMPORTANT: Mark every mentioned property or attribute with a marker:
  - [ATTR-POS] before positive attributes
  - [ATTR-NEU] before neutral attributes
  - [ATTR-NEG] before negative attributes
- Example: "PURELEI is known for [ATTR-POS] sustainable gold, [ATTR-POS] Hawaii-inspired designs and [ATTR-NEU] influencer marketing."
- Do not ask follow-up questions
- No purchase recommendations

Structure:
1. Brief context
2. Attributes with markers
3. Distinctive characteristics

Question:
{{QUESTION}}
```

**Evaluation (Type B):** list of attributes · sentiment ratio (POS/NEU/NEG) · USP match % against the brand's positioning · attributes never mentioned (gaps).

---

## CSV export schema

For tool-based tracking, export one row per prompt:

```csv
ID;Keyword;Themencluster;Fragetyp;W-Frage;Funnel_Stufe;Messziel;Tracking_Prompt
```

Compatible with Sistrix, Peec, Otterly, and Visibly AI prompt imports.
