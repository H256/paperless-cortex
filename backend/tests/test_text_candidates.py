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


# --- other EU formats and languages (about 10% of the documents) -------------------

EU_CASES = [
    # (language, text, expected issue date)
    ("en", "Acme Ltd\nInvoice date: 20 September 2026\nDue date: 04 October 2026", "2026-09-20"),
    ("en-us-order", "Invoice Date: September 20, 2026\nPayment due: October 4, 2026", "2026-09-20"),
    ("en-ordinal", "Date of issue: 20th September 2026\nDue date: 4th October 2026", "2026-09-20"),
    ("fr", "Société Martin SARL\nDate de facture : 20 septembre 2026\nÉchéance : 04/10/2026", "2026-09-20"),
    ("fr-abbr", "Date d'émission : 1er sept. 2026\nDate d'échéance : 15/10/2026", "2026-09-01"),
    ("es", "Factura\nFecha de factura: 20 de septiembre de 2026\nVencimiento: 04/10/2026", "2026-09-20"),
    ("it", "Fattura n. 12\nData fattura: 20 settembre 2026\nScadenza: 04/10/2026", "2026-09-20"),
    ("nl", "Factuurdatum: 20-09-2026\nVervaldatum: 04-10-2026", "2026-09-20"),
    ("pl", "Faktura VAT\nData wystawienia: 20 września 2026\nTermin płatności: 04.10.2026", "2026-09-20"),
    ("cz", "Faktura\nDatum vystavení: 20. září 2026\nDatum splatnosti: 04.10.2026", "2026-09-20"),
    ("da", "Faktura\nFakturadato: 20.09.2026\nForfaldsdato: 04.10.2026", "2026-09-20"),
    ("year-first-slash", "Invoice date 2026/09/20", "2026-09-20"),
]


def test_other_languages_and_formats_find_the_issue_date() -> None:
    for language, text, expected in EU_CASES:
        result = extract_date_candidates([(1, text)], today=TODAY)
        assert result, language
        assert result[0]["value"] == expected, (language, result[:3])
        assert result[0]["label"] == "issue", (language, result[0])


def test_due_and_delivery_dates_are_labelled_in_other_languages() -> None:
    text = "\n".join(
        [
            "Date de facture : 20 septembre 2026",
            "Date de livraison : 18/09/2026",
            "Date d'échéance : 04/10/2026",
        ]
    )
    result = extract_date_candidates([(1, text)], today=TODAY)
    assert _by_value(result, "2026-09-20")["label"] == "issue"
    assert _by_value(result, "2026-09-18")["label"] == "delivery"
    assert _by_value(result, "2026-10-04")["label"] == "due"


def test_slash_dates_are_day_first_unless_the_numbers_say_otherwise() -> None:
    result = extract_date_candidates(
        [(1, "Datum 20/09/2026\nDate 09/20/2026\nDate 03/04/2026")], today=TODAY
    )
    values = {c["value"] for c in result}
    assert {"2026-09-20", "2026-04-03"} <= values  # 20/09 day-first, 09/20 month-first
    assert "2026-03-04" not in values
    ambiguous = _by_value(result, "2026-04-03")
    unambiguous = _by_value(result, "2026-09-20")
    assert ambiguous["score"] <= unambiguous["score"]


def test_birth_dates_are_dropped_in_other_languages() -> None:
    text = "Né le 01/02/1980\nDate de naissance : 01.02.1980\nFecha de nacimiento 1 de febrero de 1980"
    assert extract_date_candidates([(1, text)], today=TODAY) == []


def test_numbers_that_only_look_like_dates_are_ignored() -> None:
    text = "Tel 0531-123-4567\nRechnung 2026-09-20-001\nArtikel 12-34-56"
    assert extract_date_candidates([(1, text)], today=TODAY) == []


def test_two_digit_years_are_only_accepted_with_dots() -> None:
    values = {
        c["value"]
        for c in extract_date_candidates([(1, "Datum 20.09.26\nDatum 20-09-26\nDatum 20/09/26")], today=TODAY)
    }
    assert values == {"2026-09-20"}
