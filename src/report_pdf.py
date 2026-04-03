"""PDF report generator — Visibly AI branded dark theme.

Uses fpdf2 to create a publication-ready PDF with:
- Dark cover page with orange accent bars
- KPI summary cards
- Brand ranking tables
- Model comparison tables
- Cluster analysis tables
- Visibly AI footer on every page
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

try:
    from fpdf import FPDF
except ImportError:
    logger.error("fpdf2 not installed. Run: pip install fpdf2")
    raise

from src.config import StudyConfig


# ---------------------------------------------------------------------------
# Visibly AI CI colors (RGB tuples)
# ---------------------------------------------------------------------------

C_ORANGE = (249, 115, 22)
C_DARK = (12, 17, 21)
C_NAVY = (4, 57, 89)
C_CARD = (30, 41, 59)
C_TEAL = (26, 188, 156)
C_RED = (207, 46, 46)
C_WHITE = (255, 255, 255)
C_TEXT = (226, 232, 240)
C_TEXT_MUTED = (148, 163, 184)
C_GRID = (51, 65, 85)
C_LIGHT_GRAY = (248, 248, 248)

# Font paths — use system fonts as fallback
FONT_DIR = Path(r"C:\Users\anton\OneDrive\Mabya\Dokumente\Claude\fonts")


class VisibilityPDF(FPDF):
    """Custom PDF class with Visibly AI dark theme."""

    def __init__(self, title: str = "", subtitle: str = ""):
        super().__init__()
        self.report_title = title
        self.report_subtitle = subtitle
        self._register_fonts()

    def _register_fonts(self):
        """Register Montserrat and Aptos fonts if available."""
        try:
            self.add_font("Montserrat", "", str(FONT_DIR / "Montserrat-Regular.ttf"), uni=True)
            self.add_font("Montserrat", "B", str(FONT_DIR / "Montserrat-Bold.ttf"), uni=True)
            self.add_font("Montserrat", "I", str(FONT_DIR / "Montserrat-Italic.ttf"), uni=True)
            self.add_font("Aptos", "", str(FONT_DIR / "Aptos.ttf"), uni=True)
            self.add_font("Aptos", "B", str(FONT_DIR / "Aptos-Bold.ttf"), uni=True)
            self._has_custom_fonts = True
        except Exception:
            logger.warning("Custom fonts not found, using Helvetica fallback")
            self._has_custom_fonts = False

    @property
    def heading_font(self) -> str:
        return "Montserrat" if self._has_custom_fonts else "Helvetica"

    @property
    def body_font(self) -> str:
        return "Aptos" if self._has_custom_fonts else "Helvetica"

    def header(self):
        """Dark header bar with orange accent line."""
        if self.page_no() == 1:
            return  # Cover page has its own header

        # Dark header bar
        self.set_fill_color(*C_DARK)
        self.rect(0, 0, 210, 12, "F")

        # Orange accent line
        self.set_fill_color(*C_ORANGE)
        self.rect(0, 12, 210, 0.8, "F")

        # Title text
        self.set_font(self.heading_font, "B", 8)
        self.set_text_color(*C_WHITE)
        self.set_xy(10, 3)
        self.cell(0, 6, "LLM Brand Visibility Report", align="L")

        # Page number
        self.set_xy(-40, 3)
        self.cell(30, 6, f"Page {self.page_no()}", align="R")
        self.ln(16)

    def footer(self):
        """Footer with Visibly AI branding."""
        self.set_y(-15)
        self.set_fill_color(*C_DARK)
        self.rect(0, self.get_y() - 2, 210, 20, "F")
        self.set_fill_color(*C_ORANGE)
        self.rect(0, self.get_y() - 2, 210, 0.5, "F")

        self.set_font(self.body_font, "", 7)
        self.set_text_color(*C_TEXT_MUTED)
        self.cell(0, 8, "Antonio Blago | antonioblago.com | Visibly AI", align="C")

    def add_cover(self):
        """Dark cover page with orange accent bars."""
        self.add_page()
        self.set_auto_page_break(auto=False)

        # Full dark background
        self.set_fill_color(*C_DARK)
        self.rect(0, 0, 210, 297, "F")

        # Top orange accent bar
        self.set_fill_color(*C_ORANGE)
        self.rect(0, 0, 210, 4, "F")

        # Title block
        self.set_y(80)
        self.set_font(self.heading_font, "B", 28)
        self.set_text_color(*C_WHITE)
        self.cell(0, 14, "LLM Brand Visibility", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 14, "Report", align="C", new_x="LMARGIN", new_y="NEXT")

        # Orange divider
        self.ln(5)
        self.set_fill_color(*C_ORANGE)
        self.rect(70, self.get_y(), 70, 2, "F")
        self.ln(10)

        # Subtitle
        self.set_font(self.heading_font, "", 14)
        self.set_text_color(*C_ORANGE)
        self.cell(0, 8, self.report_subtitle, align="C", new_x="LMARGIN", new_y="NEXT")

        # Date
        self.ln(5)
        self.set_font(self.body_font, "", 11)
        self.set_text_color(*C_TEXT_MUTED)
        self.cell(0, 8, datetime.now().strftime("%B %Y"), align="C", new_x="LMARGIN", new_y="NEXT")

        # Bottom accent bar
        self.set_fill_color(*C_ORANGE)
        self.rect(0, 293, 210, 4, "F")

        # Author block at bottom
        self.set_y(240)
        self.set_font(self.body_font, "", 10)
        self.set_text_color(*C_TEXT_MUTED)
        self.cell(0, 6, "Antonio Blago | SEO Consultant & AI Visibility Researcher", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 6, "antonioblago.com | visibly-ai.com", align="C", new_x="LMARGIN", new_y="NEXT")

        self.set_auto_page_break(auto=True, margin=20)

    def add_section_title(self, title: str):
        """Section title with orange left bar."""
        self.ln(5)
        y = self.get_y()
        self.set_fill_color(*C_ORANGE)
        self.rect(10, y, 3, 8, "F")
        self.set_x(17)
        self.set_font(self.heading_font, "B", 14)
        self.set_text_color(*C_WHITE)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def add_kpi_row(self, kpis: list[dict]):
        """Add a row of KPI cards. Each dict: {label, value, sub?}."""
        card_w = (190 - (len(kpis) - 1) * 5) / len(kpis)
        y_start = self.get_y()

        for i, kpi in enumerate(kpis):
            x = 10 + i * (card_w + 5)

            # Card background
            self.set_fill_color(*C_CARD)
            self.rect(x, y_start, card_w, 22, "F")

            # Orange left accent
            self.set_fill_color(*C_ORANGE)
            self.rect(x, y_start, 2, 22, "F")

            # Label
            self.set_xy(x + 5, y_start + 2)
            self.set_font(self.body_font, "", 7)
            self.set_text_color(*C_TEXT_MUTED)
            self.cell(card_w - 10, 4, kpi["label"])

            # Value
            self.set_xy(x + 5, y_start + 7)
            self.set_font(self.heading_font, "B", 14)
            self.set_text_color(*C_WHITE)
            self.cell(card_w - 10, 8, str(kpi["value"]))

            # Sub text
            if "sub" in kpi:
                self.set_xy(x + 5, y_start + 16)
                self.set_font(self.body_font, "", 7)
                self.set_text_color(*C_TEXT_MUTED)
                self.cell(card_w - 10, 4, kpi["sub"])

        self.set_y(y_start + 27)

    def add_table(self, headers: list[str], rows: list[list[str]], col_widths: list[float] | None = None):
        """Add a styled table with orange header."""
        if not col_widths:
            col_widths = [190 / len(headers)] * len(headers)

        # Header row
        self.set_fill_color(*C_ORANGE)
        self.set_text_color(*C_WHITE)
        self.set_font(self.heading_font, "B", 8)

        for i, header in enumerate(headers):
            self.cell(col_widths[i], 7, header, border=0, fill=True, align="C")
        self.ln()

        # Data rows
        self.set_font(self.body_font, "", 8)
        alternate = False

        for row in rows:
            if alternate:
                self.set_fill_color(*C_CARD)
            else:
                self.set_fill_color(*C_DARK)
            self.set_text_color(*C_TEXT)

            for i, cell_val in enumerate(row):
                self.cell(col_widths[i], 6, str(cell_val), border=0, fill=True, align="C")
            self.ln()
            alternate = not alternate

    def add_text(self, text: str, size: int = 9):
        """Add body text."""
        self.set_font(self.body_font, "", size)
        self.set_text_color(*C_TEXT_MUTED)
        self.multi_cell(0, 5, text)
        self.ln(2)


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def generate_pdf_report(
    metrics_df: pd.DataFrame,
    output_path: str | Path | None = None,
) -> str:
    """Generate a branded PDF report."""
    cfg = StudyConfig.load()
    output_path = Path(output_path) if output_path else cfg.results_dir / "report.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = metrics_df.copy()
    models = sorted(df["model"].unique())
    n_brands = df["brand"].nunique()
    n_prompts = df["prompt_id"].nunique()

    pdf = VisibilityPDF(
        title="LLM Brand Visibility Report",
        subtitle=f"Supplement Market DE — {n_brands} Brands",
    )

    # --- Page 1: Cover ---
    pdf.add_cover()

    # --- Page 2: Overview KPIs ---
    pdf.add_page()
    pdf.add_section_title("Study Overview")

    model_stats = df.groupby("model").agg(
        mention_rate=("brand_found", "mean"),
        top3_rate=("top3", "mean"),
        avg_vis=("visibility_score", "mean"),
    ).reset_index()

    pdf.add_kpi_row([
        {"label": "BRANDS TRACKED", "value": str(n_brands), "sub": "From Brand Radar"},
        {"label": "GENERIC PROMPTS", "value": str(n_prompts), "sub": "4 Clusters"},
        {"label": "LLM MODELS", "value": str(len(models)), "sub": ", ".join(m.upper() for m in models)},
        {"label": "MENTION RATE", "value": f"{df['brand_found'].mean():.1%}", "sub": "Overall Average"},
    ])

    pdf.ln(3)
    pdf.add_section_title("Model Comparison")

    pdf.add_table(
        ["Model", "Mention Rate", "Top-3 Rate", "Avg Visibility"],
        [
            [row["model"].upper(), f"{row['mention_rate']:.1%}", f"{row['top3_rate']:.1%}", f"{row['avg_vis']:.2f}"]
            for _, row in model_stats.iterrows()
        ],
        col_widths=[50, 45, 45, 50],
    )

    # --- Page 3: Brand Ranking ---
    pdf.add_page()
    pdf.add_section_title("Brand Ranking — All Models Combined")
    pdf.add_text("Top brands ranked by mention rate across all models and prompt types. "
                 "All prompts are generic — no brand names are mentioned in any prompt.")

    ranking = (
        df.groupby("brand")
        .agg(mention_rate=("brand_found", "mean"), top3_rate=("top3", "mean"),
             avg_rank=("rank_position", lambda x: x[x < 999].mean() if (x < 999).any() else None),
             avg_vis=("visibility_score", "mean"),
             times=("brand_found", "sum"))
        .reset_index()
        .sort_values("mention_rate", ascending=False)
    )

    top_rows = []
    for i, (_, row) in enumerate(ranking.head(25).iterrows(), 1):
        avg_r = f"{row['avg_rank']:.1f}" if pd.notna(row['avg_rank']) else "—"
        top_rows.append([
            f"#{i}", row["brand"], f"{row['mention_rate']:.1%}",
            f"{row['top3_rate']:.1%}", avg_r, f"{row['avg_vis']:.2f}",
        ])

    pdf.add_table(
        ["#", "Brand", "Mention", "Top-3", "Avg Rank", "Visibility"],
        top_rows,
        col_widths=[12, 50, 30, 30, 30, 38],
    )

    # --- Page 4: Per-model rankings ---
    pdf.add_page()
    pdf.add_section_title("Brand Ranking per Model")

    for model in models:
        model_data = df[df["model"] == model]
        model_ranking = (
            model_data.groupby("brand")
            .agg(mention_rate=("brand_found", "mean"), top3_rate=("top3", "mean"))
            .reset_index()
            .sort_values("mention_rate", ascending=False)
            .head(10)
        )

        pdf.ln(2)
        pdf.set_font(pdf.heading_font, "B", 11)
        pdf.set_text_color(*C_ORANGE)
        pdf.cell(0, 7, f"{model.upper()}", new_x="LMARGIN", new_y="NEXT")

        rows = []
        for i, (_, row) in enumerate(model_ranking.iterrows(), 1):
            rows.append([f"#{i}", row["brand"], f"{row['mention_rate']:.1%}", f"{row['top3_rate']:.1%}"])

        pdf.add_table(
            ["#", "Brand", "Mention Rate", "Top-3 Rate"],
            rows,
            col_widths=[12, 70, 50, 50],
        )

        if pdf.get_y() > 230:
            pdf.add_page()

    # --- Page 5: Cluster analysis ---
    pdf.add_page()
    pdf.add_section_title("Visibility by Prompt Cluster")
    pdf.add_text("Which type of query triggers the most brand mentions? "
                 "Commercial and comparison prompts typically produce more brand recommendations.")

    cluster_stats = (
        df.groupby("cluster")
        .agg(mention_rate=("brand_found", "mean"), top3_rate=("top3", "mean"),
             brands=("brand", lambda x: x[df.loc[x.index, "brand_found"] == 1].nunique()))
        .reset_index()
        .sort_values("mention_rate", ascending=False)
    )

    pdf.add_table(
        ["Cluster", "Mention Rate", "Top-3 Rate", "Brands Found"],
        [
            [row["cluster"].title(), f"{row['mention_rate']:.1%}", f"{row['top3_rate']:.1%}", str(int(row["brands"]))]
            for _, row in cluster_stats.iterrows()
        ],
        col_widths=[50, 45, 45, 50],
    )

    # --- Page 6: Brand volatility ---
    pdf.ln(5)
    pdf.add_section_title("Brand Volatility Across Models")
    pdf.add_text("Brands with high volatility have very different visibility depending on which LLM is used. "
                 "These are potential optimization targets for GEO (Generative Engine Optimization).")

    model_rates = df.pivot_table(index="brand", columns="model", values="brand_found", aggfunc="mean")
    volatility = pd.DataFrame({
        "brand": model_rates.index,
        "min_rate": model_rates.min(axis=1),
        "max_rate": model_rates.max(axis=1),
        "range": model_rates.max(axis=1) - model_rates.min(axis=1),
        "mean": model_rates.mean(axis=1),
    }).sort_values("range", ascending=False).head(15)

    pdf.add_table(
        ["Brand", "Min Rate", "Max Rate", "Range", "Mean"],
        [
            [row["brand"], f"{row['min_rate']:.1%}", f"{row['max_rate']:.1%}",
             f"{row['range']:.1%}", f"{row['mean']:.1%}"]
            for _, row in volatility.iterrows()
        ],
        col_widths=[50, 35, 35, 35, 35],
    )

    # Save
    pdf.output(str(output_path))
    logger.info(f"PDF report saved to {output_path}")
    return str(output_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate branded PDF report")
    parser.add_argument("--input", type=str, default="data/parsed_metrics.csv")
    parser.add_argument("--output", type=str, default="results/report.pdf")
    args = parser.parse_args()

    df = pd.read_csv(args.input, encoding="utf-8")
    generate_pdf_report(df, args.output)


if __name__ == "__main__":
    main()
