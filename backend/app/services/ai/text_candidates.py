"""Deterministic date and correspondent candidates computed from OCR text.

The suggestion LLM only sees text, and its date/sender guesses are sometimes wrong.
These helpers are a cheap, predictable second opinion: pure functions over text,
no LLM, no I/O. The reviewer picks a candidate explicitly; nothing is applied here.
"""

from __future__ import annotations

import datetime
import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

_MONTH_NAMES: dict[int, tuple[str, ...]] = {
    1: ("januar", "jänner", "january", "janvier", "enero", "gennaio", "januari", "janeiro",
        "stycznia", "styczeń", "ledna", "leden", "januar", "jan", "janv", "ene", "gen", "sty"),
    2: ("februar", "february", "février", "fevrier", "febrero", "febbraio", "februari",
        "fevereiro", "lutego", "luty", "února", "únor", "feb", "févr", "fevr", "lut", "úno"),
    3: ("märz", "maerz", "march", "mars", "marzo", "maart", "março", "marco", "marca", "marzec",
        "března", "březen", "mär", "mrz", "mar", "mrt", "bře"),
    4: ("april", "avril", "abril", "aprile", "kwietnia", "kwiecień", "dubna", "duben", "apr",
        "avr", "abr", "kwi", "dub"),
    5: ("mai", "may", "mayo", "maggio", "mei", "maio", "maja", "maj", "května", "květen",
        "mag", "kvě"),
    6: ("juni", "june", "juin", "junio", "giugno", "junho", "czerwca", "czerwiec", "června",
        "červen", "jun", "giu", "cze", "čvn"),
    7: ("juli", "july", "juillet", "julio", "luglio", "julho", "lipca", "lipiec", "července",
        "červenec", "jul", "juil", "lug", "lip", "čvc"),
    8: ("august", "août", "aout", "agosto", "augustus", "sierpnia", "sierpień", "srpna",
        "srpen", "aug", "ago", "sie", "srp"),
    9: ("september", "septembre", "septiembre", "setiembre", "settembre", "setembro",
        "września", "wrzesień", "wrzesnia", "září", "zari", "sep", "sept", "set", "wrz", "zář"),
    10: ("oktober", "october", "octobre", "octubre", "ottobre", "outubro", "października",
         "październik", "pazdziernika", "října", "říjen", "okt", "oct", "ott", "out", "paź", "paz",
         "říj"),
    11: ("november", "novembre", "noviembre", "novembro", "listopada", "listopad", "listopadu",
         "nov", "lis"),
    12: ("dezember", "december", "décembre", "decembre", "diciembre", "dicembre", "dezembro",
         "grudnia", "grudzień", "prosince", "prosinec", "dez", "dec", "déc", "dic", "gru", "pro"),
}
_MONTHS = {name: number for number, names in _MONTH_NAMES.items() for name in names}
_MONTH_ALT = "|".join(sorted((re.escape(m) for m in _MONTHS), key=len, reverse=True))

_SEP = r"[./-]"
# 20.09.2026, 20-09-2026, 20/09/2026 and two-digit years (day first unless disambiguated).
_NUMERIC = re.compile(rf"(?<![\d./-])(\d{{1,2}})({_SEP})\s?(\d{{1,2}})\2\s?(\d{{4}}|\d{{2}})(?!\d|-\d{{3,}})")
# 2026-09-20, 2026/09/20, 2026.09.20
_YEAR_FIRST = re.compile(rf"(?<![\d./-])(\d{{4}})({_SEP})(\d{{1,2}})\2(\d{{1,2}})(?!\d|-\d{{3,}})")
_DAY = r"(\d{1,2})(?:st|nd|rd|th|er|e|º|ª|\.)?"
_OF = r"(?:\s+(?:de|of|di|van|z|ze))?"
# 20 September 2026, 20th of September, 20. Sept. 2026, 20 de septiembre de 2026
_DAY_MONTH_YEAR = re.compile(
    rf"(?<!\d){_DAY}{_OF}\s+({_MONTH_ALT})\.?,?{_OF}\s+(\d{{4}})(?!\d)", re.IGNORECASE
)
# September 20, 2026 / Sept. 20th 2026
_MONTH_DAY_YEAR = re.compile(
    rf"(?<![^\W\d_])({_MONTH_ALT})\.?\s+{_DAY},?\s+(\d{{4}})(?!\d)", re.IGNORECASE
)

# Keyword groups, matched against the text right before (and just after) a date.
# German first, then the languages of the EU invoices that show up most often.
_ISSUE_STRONG = (
    "rechnungsdatum", "belegdatum", "ausstellungsdatum", "invoice date", "date of issue",
    "issue date", "date d'émission", "date d\u2019émission", "date de facture", "date de la facture",
    "fecha de emisión", "fecha de factura", "data di emissione", "data fattura",
    "data della fattura", "factuurdatum", "data wystawienia", "data faktury",
    "datum vystavení", "datum vydání", "fakturadato", "fakturadatum", "data de emissão",
    "data da fatura", "invoice no. date", "tax invoice date",
)
_ISSUE_KEYWORDS = (
    "rechnung vom", "ausgestellt", "datum", "date", "bescheid vom", "schreiben vom",
    "bestätigung vom", "gutschrift vom", "angebot vom", "erstellt am", "vom", "dated",
    "issued", "fecha", "data", "dato", "dnia",
)
_DELIVERY_KEYWORDS = (
    "lieferdatum", "versanddatum", "leistungsdatum", "leistungszeitpunkt", "lieferung", "liefertermin",
    "bestelldatum", "auftragsdatum", "bestellt am", "versand", "termin", "delivery date",
    "date of supply", "supply date", "order date", "shipping date", "dispatch date",
    "date de livraison", "date de commande", "fecha de entrega", "fecha de pedido",
    "data di consegna", "data dell'ordine", "leverdatum", "besteldatum", "data dostawy",
    "data sprzedaży", "datum dodání", "datum zdanitelného plnění", "leveringsdato",
    "leveransdatum", "data de entrega",
)
_DUE_KEYWORDS = (
    "fällig", "fälligkeit", "fälligkeitsdatum", "faellig", "zahlbar bis", "zahlungsziel", "zahlungsfrist", "bis zum",
    "spätestens", "frist", "zahlen sie bis", "due", "pay by", "payable by", "payment due",
    "date d'échéance", "échéance", "echeance", "à payer avant", "payable avant",
    "fecha de vencimiento", "vencimiento", "pagar antes", "scadenza", "data di scadenza",
    "pagabile entro", "vervaldatum", "uiterlijk", "betaaldatum", "termin płatności",
    "termin platnosci", "płatne do", "datum splatnosti", "splatnost", "forfaldsdato",
    "förfallodatum", "förfallodag", "data de vencimento", "vencimento",
)
_PERIOD_KEYWORDS = (
    "zeitraum", "abrechnungszeitraum", "leistungszeitraum", "von", "bis", "period",
    "période", "periode", "periodo", "okres",
)
_BIRTH_KEYWORDS = (
    "geboren", "geb.", "geburtsdatum", "geburtstag", "born", "date of birth", "dob",
    "né le", "née le", "date de naissance", "fecha de nacimiento", "nacido",
    "data di nascita", "nato il", "geboortedatum", "geboren op", "data urodzenia",
    "data de nascimento", "datum narození", "fødselsdato", "födelsedatum",
)
_PRINT_KEYWORDS = (
    "druckdatum", "gedruckt", "ausdruck", "printed", "print date", "date d'impression",
    "fecha de impresión", "data di stampa", "afgedrukt",
)

_MIN_YEAR = 1950
_FUTURE_TOLERANCE_DAYS = 366

_LEGAL_FORM_RE = re.compile(
    r"\b(gmbh|ag|kg|ohg|ug|e\.\s?v\.|gbr|mbh|se|inc\.?|ltd\.?|llc|sarl|b\.\s?v\.|eg|e\.\s?k\.|kgaa|plc)\b",
    re.IGNORECASE,
)


@dataclass
class _DateHit:
    value: datetime.date
    raw: str
    line: str
    line_index: int
    page: int | None
    label: str
    score: float


@dataclass
class _Aggregate:
    best: _DateHit
    occurrences: int = 1
    labels: set[str] = field(default_factory=set)


def _fold(text: str) -> str:
    """Lower-case, strip accents and collapse whitespace for matching."""
    normalized = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped.replace("ß", "ss")).strip()


def _make_date(day: int, month: int, year: int, today: datetime.date) -> datetime.date | None:
    if year < 100:
        year += 2000 if year < 70 else 1900
    try:
        value = datetime.date(year, month, day)
    except ValueError:
        return None
    if value.year < _MIN_YEAR:
        return None
    if value > today + datetime.timedelta(days=_FUTURE_TOLERANCE_DAYS):
        return None
    return value


def _numeric_value(
    first: int, second: int, year: int, sep: str, today: datetime.date
) -> tuple[datetime.date | None, str]:
    """Interpret ``first sep second sep year``; day first unless the numbers say otherwise."""
    if sep == "/" and first <= 12 and second > 12:
        return _make_date(second, first, year, today), "us"  # 09/20/2026
    value = _make_date(first, second, year, today)
    if value is not None and sep == "/" and first <= 12 and second <= 12 and first != second:
        return value, "ambiguous"  # 03/04/2026: day/month assumed, could be month/day
    return value, "numeric"


def _iter_dates(line: str, today: datetime.date):
    for match in _YEAR_FIRST.finditer(line):
        value = _make_date(int(match[4]), int(match[3]), int(match[1]), today)
        if value:
            yield value, match.span(), match.group(0), "iso"
    for match in _NUMERIC.finditer(line):
        first, sep, second, year_raw = int(match[1]), match[2], int(match[3]), match[4]
        if len(year_raw) == 2 and sep != ".":
            continue  # 10-12-24 or 10/12/24 is too ambiguous to be useful
        value, kind = _numeric_value(first, second, int(year_raw), sep, today)
        if value:
            yield value, match.span(), match.group(0), kind
    for match in _DAY_MONTH_YEAR.finditer(line):
        month = _MONTHS.get(match[2].lower())
        if month:
            value = _make_date(int(match[1]), month, int(match[3]), today)
            if value:
                yield value, match.span(), match.group(0), "wordy"
    for match in _MONTH_DAY_YEAR.finditer(line):
        month = _MONTHS.get(match[1].lower())
        if month:
            value = _make_date(int(match[2]), month, int(match[3]), today)
            if value:
                yield value, match.span(), match.group(0), "wordy"


def _last_keyword_end(window: str, keywords: tuple[str, ...]) -> int:
    """End index of the last keyword occurrence in ``window`` (-1 if none)."""
    end = -1
    for kw in keywords:
        for match in re.finditer(rf"(?<![^\W\d_]){re.escape(kw)}(?![^\W\d_])", window):
            end = max(end, match.end())
    return end


# Ordered by priority for ties; (label, score adjustment, keywords).
_GROUPS: tuple[tuple[str, float, tuple[str, ...]], ...] = (
    ("due", -0.3, _DUE_KEYWORDS),
    ("delivery", -0.1, _DELIVERY_KEYWORDS),
    ("other", -0.15, _PRINT_KEYWORDS),
    ("issue", 0.45, _ISSUE_STRONG),
    ("issue", 0.3, _ISSUE_KEYWORDS),
    ("period", -0.1, _PERIOD_KEYWORDS),
)


def _classify(before: str, after: str) -> tuple[str, float] | None:
    """Return (label, score adjustment) for the text around a date, or None to drop it.

    The keyword closest to the date wins, so "Zahlbar bis 19.09. Rechnungsdatum
    05.09." classifies each date by its own label.
    """
    near = before[-48:].lower()
    follow = after[:16].lower()
    if _last_keyword_end(near, _BIRTH_KEYWORDS) >= 0 or "(geb" in follow:
        return None
    best: tuple[int, str, float] | None = None
    for label, adjustment, keywords in _GROUPS:
        end = _last_keyword_end(near, keywords)
        if end < 0:
            continue
        if best is None or end > best[0]:
            best = (end, label, adjustment)
    if best is None:
        return "other", 0.0
    return best[1], best[2]


def extract_date_candidates(
    pages: list[tuple[int | None, str]],
    *,
    today: datetime.date | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Rank date occurrences found in ``pages`` as candidates for the issue date.

    ``pages`` is a list of ``(page_number, text)``. Returns dicts with ``value``
    (ISO date), ``label`` (issue / delivery / due / period / other), ``score``,
    ``context`` (the line it was found in), ``page`` and ``occurrences``.
    """
    reference = today or datetime.date.today()
    aggregates: dict[datetime.date, _Aggregate] = {}

    for page, text in pages:
        lines = (text or "").splitlines()
        non_empty_index = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            for value, (start, end), raw, kind in _iter_dates(stripped, reference):
                verdict = _classify(stripped[:start], stripped[end:])
                if verdict is None:
                    continue
                label, adjustment = verdict
                score = 0.5 + adjustment
                if kind in {"ambiguous", "us"}:
                    score -= 0.05  # DD/MM vs MM/DD is ambiguous
                if non_empty_index < 15:
                    score += 0.1 * (1 - non_empty_index / 15)
                if (page or 1) == 1:
                    score += 0.05
                score = max(0.0, min(1.0, score))
                hit = _DateHit(value, raw, stripped, non_empty_index, page, label, score)
                existing = aggregates.get(value)
                if existing is None:
                    aggregates[value] = _Aggregate(best=hit, labels={label})
                else:
                    existing.occurrences += 1
                    existing.labels.add(label)
                    if hit.score > existing.best.score:
                        existing.best = hit
            non_empty_index += 1

    ranked = sorted(
        aggregates.values(),
        key=lambda agg: (agg.best.score + min(0.1, 0.03 * (agg.occurrences - 1)), agg.best.value),
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    for agg in ranked[:limit]:
        hit = agg.best
        out.append(
            {
                "value": hit.value.isoformat(),
                "label": hit.label,
                "score": round(min(1.0, hit.score + min(0.1, 0.03 * (agg.occurrences - 1))), 3),
                "context": hit.line[:160],
                "page": hit.page,
                "occurrences": agg.occurrences,
            }
        )
    return out


_CONTACT_RE = re.compile(r"\S+@\S+|(?:https?://|www\.)\S+", re.IGNORECASE)


def _normalize_name(name: str) -> str:
    # E-mail addresses and URLs are a separate (weaker) signal, see _domain_stems.
    folded = _fold(_CONTACT_RE.sub(" ", name))
    folded = _LEGAL_FORM_RE.sub(" ", folded)
    folded = re.sub(r"[^a-z0-9 ]+", " ", folded)
    return re.sub(r"\s+", " ", folded).strip()


def _domain_stems(text: str) -> set[str]:
    stems: set[str] = set()
    for match in re.finditer(r"(?:@|https?://|www\.)([a-z0-9-]+(?:\.[a-z0-9-]+)*)", text.lower()):
        parts = [p for p in match.group(1).split(".") if p and p not in {"www", "mail"}]
        if len(parts) >= 2:
            stems.add(parts[-2].replace("-", ""))
        elif parts:
            stems.add(parts[0].replace("-", ""))
    return stems


def extract_correspondent_candidates(
    pages: list[tuple[int | None, str]],
    known_correspondents: list[str],
    *,
    header_lines: int = 30,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Match known correspondents against the text and propose at most one new name.

    Returns dicts with ``name``, ``known`` (exists in Paperless), ``score``,
    ``evidence`` (header / text / domain / legal_form) and ``context``.
    """
    all_lines: list[str] = []
    for _, text in pages:
        all_lines.extend(ln.strip() for ln in (text or "").splitlines() if ln.strip())
    if not all_lines:
        return []
    header = all_lines[:header_lines]
    header_norm = [_normalize_name(ln) for ln in header]
    full_norm = _normalize_name(" ".join(all_lines))
    domains = _domain_stems("\n".join(all_lines))

    results: dict[str, dict[str, Any]] = {}

    def offer(name: str, score: float, evidence: str, context: str, known: bool) -> None:
        current = results.get(name)
        if current is None or score > current["score"]:
            results[name] = {
                "name": name,
                "known": known,
                "score": round(min(1.0, score), 3),
                "evidence": evidence,
                "context": context[:160],
            }

    for name in known_correspondents:
        if not isinstance(name, str) or not name.strip():
            continue
        norm = _normalize_name(name)
        if len(norm) < 4:
            continue
        tokens = [t for t in norm.split(" ") if len(t) > 1]
        # 1) the name appears in a header line
        matched_header = False
        for idx, line_norm in enumerate(header_norm):
            if not line_norm:
                continue
            if re.search(rf"(?<![a-z0-9]){re.escape(norm)}(?![a-z0-9])", line_norm):
                offer(name, 0.92 - min(0.12, idx * 0.004), "header", header[idx], True)
                matched_header = True
                break
            if len(tokens) >= 2 and all(tok in line_norm.split(" ") for tok in tokens):
                offer(name, 0.82 - min(0.1, idx * 0.004), "header", header[idx], True)
                matched_header = True
                break
            ratio = difflib.SequenceMatcher(None, norm, line_norm).ratio()
            if ratio >= 0.86 and abs(len(norm) - len(line_norm)) <= max(4, len(norm) // 3):
                offer(name, 0.72 * ratio, "header", header[idx], True)
                matched_header = True
                break
        if matched_header:
            continue
        # 2) the name appears anywhere in the text
        if re.search(rf"(?<![a-z0-9]){re.escape(norm)}(?![a-z0-9])", full_norm):
            count = len(re.findall(rf"(?<![a-z0-9]){re.escape(norm)}(?![a-z0-9])", full_norm))
            offer(name, 0.6 + min(0.1, 0.03 * (count - 1)), "text", name, True)
            continue
        # 3) a website / e-mail domain contains the main token of the name
        main = max(tokens, key=len) if tokens else ""
        compact = "".join(tokens)
        if main and len(main) >= 4 and any(stem in (compact, main) for stem in domains):
            offer(name, 0.5, "domain", name, True)

    # A new, unknown sender is only proposed from a header line that carries a legal form.
    if not any(item["evidence"] == "header" and item["score"] >= 0.8 for item in results.values()):
        for line in header[:12]:
            if _LEGAL_FORM_RE.search(line) and 4 <= len(line) <= 80 and not re.search(r"\d{5}", line):
                cleaned = re.sub(r"\s{2,}", " ", line).strip(" ,;:-")
                known_lower = {n.lower() for n in known_correspondents if isinstance(n, str)}
                if cleaned.lower() not in known_lower:
                    offer(cleaned, 0.45, "legal_form", line, False)
                break

    ranked = sorted(results.values(), key=lambda item: item["score"], reverse=True)
    return ranked[:limit]


def candidates_from_sources(
    sources: dict[str, list[tuple[int | None, str]]],
    known_correspondents: list[str],
    *,
    today: datetime.date | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Run the extractors per OCR source and merge the results.

    Occurrences are not added up across sources (the same text read twice is not
    two occurrences); the best score wins and the contributing sources are listed.
    """
    dates: dict[str, dict[str, Any]] = {}
    correspondents: dict[str, dict[str, Any]] = {}
    for source, pages in sources.items():
        for item in extract_date_candidates(pages, today=today):
            current = dates.get(item["value"])
            if current is None:
                dates[item["value"]] = {**item, "sources": [source]}
                continue
            current["sources"].append(source)
            current["occurrences"] = max(current["occurrences"], item["occurrences"])
            if item["score"] > current["score"]:
                current.update(
                    {k: item[k] for k in ("label", "score", "context", "page")},
                )
        for item in extract_correspondent_candidates(pages, known_correspondents):
            current = correspondents.get(item["name"])
            if current is None:
                correspondents[item["name"]] = {**item, "sources": [source]}
                continue
            current["sources"].append(source)
            if item["score"] > current["score"]:
                current.update({k: item[k] for k in ("score", "evidence", "context")})
    return {
        "dates": sorted(dates.values(), key=lambda c: (c["score"], c["value"]), reverse=True)[:8],
        "correspondents": sorted(correspondents.values(), key=lambda c: c["score"], reverse=True)[
            :5
        ],
    }

