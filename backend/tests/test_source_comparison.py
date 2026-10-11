from __future__ import annotations

import pytest

from app.services.ai.source_comparison import readability, recommend_source, token_agreement


def test_identical_texts_agree_fully() -> None:
    text = "Rechnung Getränkemarkt Gesamtbetrag 39,16 Euro bezahlt per PayPal"
    assert token_agreement(text, text) == 1.0


def test_case_and_short_tokens_are_ignored() -> None:
    # shared: rechnung, firma; union: rechnung, der, die, firma
    assert token_agreement("Rechnung der Firma", "RECHNUNG die firma") == 0.5
    assert token_agreement("ab cd", "ab cd") is None  # no word with >= 3 characters


def test_scrambled_text_has_low_agreement() -> None:
    clean = "Lieferanschrift Herr Klemens Wittig Koldeweystraße Braunschweig Marktnummer"
    garbage = "nei xqz qpl Geschäftsführer Henze Walter Friedrich Gerlach"
    value = token_agreement(clean, garbage)
    assert value is not None
    assert value < 0.2


def test_missing_text_gives_no_agreement() -> None:
    assert token_agreement("", "Rechnung Betrag") is None
    assert token_agreement(None, None) is None


def test_readability_is_the_inverse_of_the_penalty() -> None:
    assert readability(6.14) == pytest.approx(93.86)
    assert readability(150) == 0.0
    assert readability(-5) == 100.0
    assert readability(None) is None


def test_recommend_prefers_the_cleaner_text() -> None:
    result = recommend_source(
        [
            {"source": "paperless_ocr", "quality_score": 30.0},
            {"source": "vision_ocr", "quality_score": 4.5},
        ]
    )
    assert result["source"] == "vision_ocr"
    assert "Readability" in str(result["reason"])


def test_recommend_makes_no_call_when_sources_are_close() -> None:
    result = recommend_source(
        [
            {"source": "paperless_ocr", "quality_score": 6.1},
            {"source": "vision_ocr", "quality_score": 4.5},
        ],
        agreement=0.3,
    )
    assert result["source"] is None
    assert "differ a lot" in str(result["reason"])


def test_recommend_handles_one_or_no_score() -> None:
    assert recommend_source([])["source"] is None
    only = recommend_source([{"source": "paperless_ocr", "quality_score": 10.0}])
    assert only["source"] == "paperless_ocr"
