from __future__ import annotations

import datetime

from app.services.ai.text_candidates import (
    extract_correspondent_candidates,
    extract_date_candidates,
)

TODAY = datetime.date(2026, 10, 11)

INVOICE = """Lautsprecher Teufel GmbH
Bikini Berlin, Budapester Str. 44
10787 Berlin

Rechnung Nr. 6005603054
Rechnungsdatum: 20.09.2026
Lieferdatum: 18.09.2026
Zahlbar bis 04.10.2026
Kunde geboren am 01.02.1980
"""


def _by_value(candidates: list[dict], value: str) -> dict:
    return next(c for c in candidates if c["value"] == value)


def test_invoice_date_ranks_above_delivery_and_due_dates() -> None:
    result = extract_date_candidates([(1, INVOICE)], today=TODAY)

    assert result[0]["value"] == "2026-09-20"
    assert result[0]["label"] == "issue"
    assert _by_value(result, "2026-09-18")["label"] == "delivery"
    assert _by_value(result, "2026-10-04")["label"] == "due"
    assert result[0]["score"] > _by_value(result, "2026-09-18")["score"]
    assert result[0]["context"].startswith("Rechnungsdatum")
    assert result[0]["page"] == 1


def test_birth_dates_are_not_candidates() -> None:
    result = extract_date_candidates([(1, INVOICE)], today=TODAY)
    assert all(c["value"] != "1980-02-01" for c in result)


def test_supported_formats_are_normalized() -> None:
    text = "\n".join(
        [
            "Datum: 5. September 2026",
            "Ausgestellt am 2026-08-30",
            "Stand 3.4.26",
            "Termin 12/11/2026",
        ]
    )
    values = {c["value"] for c in extract_date_candidates([(1, text)], today=TODAY)}
    assert {"2026-09-05", "2026-08-30", "2026-04-03", "2026-11-12"} <= values


def test_nearest_keyword_wins_on_a_single_line() -> None:
    text = "Zahlbar bis 19.09.2026   Rechnungsdatum 05.09.2026"
    result = extract_date_candidates([(1, text)], today=TODAY)
    assert _by_value(result, "2026-09-05")["label"] == "issue"
    assert _by_value(result, "2026-09-19")["label"] == "due"


def test_invalid_and_far_future_dates_are_dropped() -> None:
    text = "Datum 31.02.2026\nDatum 01.01.2099\nDatum 01.01.1900"
    assert extract_date_candidates([(1, text)], today=TODAY) == []


def test_repeated_dates_are_merged_and_counted() -> None:
    text = "Datum 20.09.2026\nSeite 2 Datum 20.09.2026"
    result = extract_date_candidates([(1, text)], today=TODAY)
    assert len(result) == 1
    assert result[0]["occurrences"] == 2


def test_known_correspondent_in_header_is_ranked_first() -> None:
    known = ["Telekom Deutschland GmbH", "Lautsprecher Teufel GmbH", "Hornbach Baumarkt"]
    result = extract_correspondent_candidates([(1, INVOICE)], known)

    assert result[0]["name"] == "Lautsprecher Teufel GmbH"
    assert result[0]["known"] is True
    assert result[0]["evidence"] == "header"
    assert all(c["name"] != "Telekom Deutschland GmbH" for c in result)


def test_legal_form_and_punctuation_are_ignored_when_matching() -> None:
    text = "Lautsprecher Teufel\nKundenservice\nRechnung"
    result = extract_correspondent_candidates([(1, text)], ["Lautsprecher Teufel GmbH"])
    assert result and result[0]["name"] == "Lautsprecher Teufel GmbH"


def test_unknown_sender_is_proposed_from_a_legal_form_line() -> None:
    text = "Musterfirma Digital GmbH\nHauptstr. 1\n38100 Braunschweig\nRechnung"
    result = extract_correspondent_candidates([(1, text)], ["Hornbach Baumarkt"])
    assert result[0]["name"] == "Musterfirma Digital GmbH"
    assert result[0]["known"] is False
    assert result[0]["evidence"] == "legal_form"


def test_domain_hint_matches_known_correspondent() -> None:
    text = "Rechnung\nKontakt: service@hornbach.de\nVielen Dank"
    result = extract_correspondent_candidates([(1, text)], ["Hornbach"])
    assert result and result[0]["name"] == "Hornbach"
    assert result[0]["evidence"] in {"domain", "text"}


def test_empty_text_yields_no_candidates() -> None:
    assert extract_date_candidates([(1, "")], today=TODAY) == []
    assert extract_correspondent_candidates([(1, "   ")], ["Hornbach"]) == []
