from __future__ import annotations

from app.config import load_settings
from app.services.documents.text_pages import _is_vowel, score_text_quality


def test_accented_letters_are_vowels() -> None:
    for ch in "aeiouäöüéèàíóúůő":
        assert _is_vowel(ch), ch
    for ch in "bcdfgłñçß1 .":
        assert not _is_vowel(ch), ch


def test_foreign_language_text_is_not_penalized_for_accents() -> None:
    settings = load_settings()
    french = (
        "Facture numéro 2026-0417. Merci pour votre commande passée le 10 octobre. "
        "Le montant total à régler est de 39,16 euros, livraison à l'adresse indiquée. "
        "Nous vous remercions de votre confiance et restons à votre disposition."
    )
    quality = score_text_quality(french, settings)

    assert quality.score >= 90
    assert "low_wordlike_ratio" not in quality.reasons
    assert quality.metrics["word_count"] > 20


def test_accents_stay_inside_their_word() -> None:
    settings = load_settings()
    quality = score_text_quality("café façade señor żółć " * 6, settings)
    # "café" is one word instead of being split at the accent
    assert quality.metrics["word_count"] == 24


def test_garbage_is_still_penalized() -> None:
    settings = load_settings()
    quality = score_text_quality("xqz bcdfg hjklm npqrst vwxz " * 8, settings)
    assert quality.score < 80
