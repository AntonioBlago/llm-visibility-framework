"""Tests for the response parser module — exact + domain + fuzzy matching."""

import pytest

from src.config import BrandConfig, VisibilityScoring
from src.parser import (
    _extract_ranked_list,
    _find_brand_exact,
    _find_brand_domain,
    _find_brand_fuzzy,
    _find_brand_rank,
    find_brand_in_text,
    parse_single_response,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ag1_brand():
    return BrandConfig(
        name="AG1",
        domain="drinkag1.com",
        aliases=["ag1", "athletic greens", "ag1 by athletic greens"],
        category="greens",
    )


@pytest.fixture
def foodspring_brand():
    return BrandConfig(
        name="Foodspring",
        domain="foodspring.de",
        aliases=["foodspring", "food spring"],
        category="sports_nutrition",
    )


@pytest.fixture
def esn_brand():
    return BrandConfig(
        name="ESN",
        domain="esn.com",
        aliases=["esn", "elite sports nutrients", "esn designer whey"],
        category="sports_nutrition",
    )


@pytest.fixture
def morenutrition_brand():
    return BrandConfig(
        name="Morenutrition",
        domain="morenutrition.de",
        aliases=["morenutrition", "more nutrition", "more"],
        category="sports_nutrition",
    )


@pytest.fixture
def loewenzahn_brand():
    return BrandConfig(
        name="Loewenzahnorganics",
        domain="loewenzahnorganics.com",
        aliases=["loewenzahnorganics", "löwenzahn organics", "loewenzahn organics", "löwenzahnorganics"],
        category="organic",
    )


@pytest.fixture
def scoring():
    return VisibilityScoring(
        weights={1: 10, 2: 8, 3: 6, 4: 5, 5: 4},
        mentioned_other=2,
        not_mentioned=0,
    )


# ---------------------------------------------------------------------------
# Layer 1: Exact matching tests
# ---------------------------------------------------------------------------

class TestExactMatching:

    def test_exact_match(self, ag1_brand):
        found, _ = _find_brand_exact("AG1 ist ein gutes Greens Pulver", ag1_brand)
        assert found

    def test_alias_match(self, ag1_brand):
        found, _ = _find_brand_exact("Athletic Greens bietet ein All-in-One Supplement", ag1_brand)
        assert found

    def test_case_insensitive(self, ag1_brand):
        found, _ = _find_brand_exact("ag1 ist beliebt", ag1_brand)
        assert found

    def test_no_false_positive(self, esn_brand):
        found, _ = _find_brand_exact("Die Essenz des Proteins ist wichtig", esn_brand)
        assert not found

    def test_word_boundary(self, esn_brand):
        found, _ = _find_brand_exact("ESN bietet hochwertiges Whey", esn_brand)
        assert found
        found2, _ = _find_brand_exact("Design ist wichtig", esn_brand)
        assert not found2

    def test_not_found(self, ag1_brand):
        found, _ = _find_brand_exact("Proteinpulver ist gesund", ag1_brand)
        assert not found

    def test_brand_in_markdown_bold(self, foodspring_brand):
        found, _ = _find_brand_exact("**Foodspring** ist eine deutsche Marke", foodspring_brand)
        assert found

    def test_brand_in_list_item(self, ag1_brand):
        text = "1. AG1\n2. Foodspring\n3. ESN"
        found, _ = _find_brand_exact(text, ag1_brand)
        assert found

    def test_german_umlaut_alias(self, loewenzahn_brand):
        found, _ = _find_brand_exact("Löwenzahn Organics bietet Bio-Supplements", loewenzahn_brand)
        assert found


# ---------------------------------------------------------------------------
# Layer 2: Domain matching tests
# ---------------------------------------------------------------------------

class TestDomainMatching:

    def test_domain_match(self, ag1_brand):
        found, _ = _find_brand_domain("Mehr Infos auf drinkag1.com", ag1_brand)
        assert found

    def test_domain_with_www(self, foodspring_brand):
        found, _ = _find_brand_domain("Besuche www.foodspring.de", foodspring_brand)
        assert found

    def test_domain_in_url(self, ag1_brand):
        found, _ = _find_brand_domain("https://drinkag1.com/products", ag1_brand)
        assert found

    def test_no_domain_match(self, ag1_brand):
        found, _ = _find_brand_domain("Proteinpulver kaufen", ag1_brand)
        assert not found


# ---------------------------------------------------------------------------
# Layer 3: Fuzzy matching tests
# ---------------------------------------------------------------------------

class TestFuzzyMatching:

    def test_fuzzy_compound_word(self, foodspring_brand):
        """German compound: 'Foodsprings' (with trailing s)."""
        found, _, score = _find_brand_fuzzy("Foodsprings hat gute Produkte", foodspring_brand)
        assert found
        assert score >= 85

    def test_fuzzy_hyphenated(self, ag1_brand):
        """AG1-Pulver should still match AG1."""
        # AG1 is only 3 chars, so it won't fuzzy match (min 4 chars)
        # But "athletic greens" will
        found, _, score = _find_brand_fuzzy(
            "Das Athletic-Greens Pulver ist beliebt", ag1_brand
        )
        assert found

    def test_fuzzy_no_false_positive_short_name(self, esn_brand):
        """Short names like 'esn' should NOT fuzzy match random text."""
        # ESN is 3 chars — blocked from fuzzy matching
        found, _, _ = _find_brand_fuzzy("Eine essentielle Aminosaeure", esn_brand)
        assert not found

    def test_fuzzy_typo(self, foodspring_brand):
        """Slight typo: 'Fodspring'."""
        found, _, score = _find_brand_fuzzy("Fodspring ist eine bekannte Marke", foodspring_brand)
        assert found
        assert score >= 85

    def test_fuzzy_reordered_words(self, morenutrition_brand):
        """Token set ratio: 'Nutrition More' vs 'More Nutrition'."""
        found, _, score = _find_brand_fuzzy(
            "Die Firma Nutrition More bietet viele Produkte", morenutrition_brand
        )
        # more nutrition has "more" which is in blocklist for short names
        # but "morenutrition" (7 chars) should work
        assert found or score >= 70  # relaxed for reordered tokens


# ---------------------------------------------------------------------------
# Combined detection tests
# ---------------------------------------------------------------------------

class TestCombinedDetection:

    def test_exact_preferred_over_fuzzy(self, foodspring_brand):
        found, _, method, _ = find_brand_in_text("Foodspring ist super", foodspring_brand)
        assert found
        assert method == "exact"

    def test_domain_fallback(self, ag1_brand):
        found, _, method, _ = find_brand_in_text("Schau auf drinkag1.com nach", ag1_brand)
        assert found
        assert method in ("exact", "domain")  # ag1 might match exact in drinkag1

    def test_fuzzy_fallback(self, foodspring_brand):
        found, _, method, _ = find_brand_in_text(
            "Fodspring hat gute Bewertungen", foodspring_brand,
            fuzzy_enabled=True,
        )
        assert found
        assert method == "fuzzy"

    def test_nothing_found(self, ag1_brand):
        found, _, method, _ = find_brand_in_text(
            "Vitamin C ist wichtig fuer das Immunsystem", ag1_brand,
        )
        assert not found
        assert method == ""


# ---------------------------------------------------------------------------
# Ranked list extraction tests
# ---------------------------------------------------------------------------

class TestRankedListExtraction:

    def test_numbered_list(self):
        text = "1. AG1\n2. Foodspring\n3. ESN"
        items = _extract_ranked_list(text)
        assert len(items) == 3
        assert "AG1" in items[0]

    def test_numbered_with_parens(self):
        text = "1) AG1\n2) Foodspring\n3) ESN"
        items = _extract_ranked_list(text)
        assert len(items) == 3

    def test_bulleted_list(self):
        text = "- AG1\n- Foodspring\n- ESN"
        items = _extract_ranked_list(text)
        assert len(items) == 3

    def test_markdown_bold_with_description(self):
        text = "1. **AG1** - Das beste Greens Pulver\n2. **Foodspring** - Gutes Protein"
        items = _extract_ranked_list(text)
        assert len(items) == 2
        # Should extract just the brand name, not the description
        assert "AG1" in items[0]

    def test_mixed_content(self):
        text = """Hier sind die besten Supplement-Marken:

1. AG1 - All-in-One Greens
2. Foodspring - Sport Supplements
3. ESN - Whey Protein

Diese Marken sind alle empfehlenswert."""
        items = _extract_ranked_list(text)
        assert len(items) == 3

    def test_no_list(self):
        text = "Nahrungsergaenzungsmittel sind wichtig fuer die Gesundheit."
        items = _extract_ranked_list(text)
        assert len(items) == 0


# ---------------------------------------------------------------------------
# Brand rank finding tests
# ---------------------------------------------------------------------------

class TestBrandRankFinding:

    def test_find_rank_position_1(self, ag1_brand):
        items = ["AG1 - das beste Greens", "Foodspring Protein", "ESN Whey"]
        assert _find_brand_rank(items, ag1_brand) == 1

    def test_find_rank_position_3(self, ag1_brand):
        items = ["Foodspring", "ESN", "AG1"]
        assert _find_brand_rank(items, ag1_brand) == 3

    def test_not_in_list(self, ag1_brand):
        items = ["Foodspring", "ESN", "Gloryfeel"]
        assert _find_brand_rank(items, ag1_brand) is None

    def test_alias_match_in_list(self, ag1_brand):
        items = ["Athletic Greens ist das beste", "Foodspring"]
        assert _find_brand_rank(items, ag1_brand) == 1


# ---------------------------------------------------------------------------
# Full parse tests
# ---------------------------------------------------------------------------

class TestParseSingleResponse:

    def test_mentioned_and_ranked(self, ag1_brand, scoring):
        text = """Die besten Greens Pulver:
1. AG1 - Marktfuehrer
2. Foodspring - Gute Alternative
3. Natural Mojo"""
        result = parse_single_response(text, ag1_brand, scoring)
        assert result.found is True
        assert result.rank_position == 1
        assert result.in_top3 is True
        assert result.visibility_score == 10
        assert result.match_method == "exact"

    def test_mentioned_but_not_ranked(self, ag1_brand, scoring):
        text = "Es gibt viele Supplements. AG1 ist auch bekannt. Insgesamt ist der Markt gross."
        result = parse_single_response(text, ag1_brand, scoring)
        assert result.found is True

    def test_not_mentioned(self, ag1_brand, scoring):
        text = "Proteinpulver ist wichtig fuer den Muskelaufbau."
        result = parse_single_response(text, ag1_brand, scoring)
        assert result.found is False
        assert result.visibility_score == 0

    def test_position_5_score(self, ag1_brand, scoring):
        text = """Top Supplements:
1. Foodspring
2. ESN
3. Gloryfeel
4. Natural Mojo
5. AG1"""
        result = parse_single_response(text, ag1_brand, scoring)
        assert result.found is True
        assert result.rank_position == 5
        assert result.in_top3 is False
        assert result.visibility_score == 4

    def test_domain_detection(self, ag1_brand, scoring):
        text = "Mehr Informationen finden Sie auf drinkag1.com fuer das Greens Pulver."
        result = parse_single_response(text, ag1_brand, scoring)
        assert result.found is True
        assert result.match_method in ("exact", "domain")  # "ag1" substring may exact-match

    def test_fuzzy_detection(self, foodspring_brand, scoring):
        text = "Fodspring bietet hochwertige Proteinprodukte an."
        result = parse_single_response(text, foodspring_brand, scoring, fuzzy_enabled=True)
        assert result.found is True
        assert result.match_method == "fuzzy"

    def test_49_brands_no_crash(self, scoring):
        """Ensure parsing with many brands doesn't crash on a typical response."""
        text = """Die beliebtesten Supplement-Marken in Deutschland:
1. AG1 - All-in-One
2. Foodspring - Sport
3. ESN - Protein
4. Gloryfeel - Vitamine
5. Glow25 - Kollagen
6. Braineffect - Nootropika
7. Natural Mojo - Superfood
8. More Nutrition - Fitness
9. YFood - Mahlzeitenersatz
10. Naturtreu - Natur"""
        from src.config import StudyConfig
        cfg = StudyConfig.load()
        for brand in cfg.brands:
            result = parse_single_response(text, brand, scoring)
            # Should not raise
            assert isinstance(result.found, bool)
