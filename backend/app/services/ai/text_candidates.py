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

_MONTHS = {
    "januar": 1, "jan": 1, "january": 1,
    "februar": 2, "feb": 2, "february": 2,
    "märz": 3, "maerz": 3, "mär": 3, "mrz": 3, "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mai": 5, "may": 5,
    "juni": 6, "jun": 6, "june": 6,
    "juli": 7, "jul": 7, "july": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "dezember": 12, "dez": 12, "december": 12, "dec": 12,
}
_MONTH_ALT = "|".join(sorted((re.escape(m) for m in _MONTHS), key=len, reverse=True))

_NUMERIC_DE = re.compile(r"(?<![\d.])(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4}|\d{2})(?![\d])")
_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])")
_SLASH = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4})(?![\d/])")
_WORDY = re.compile(rf"(?<!\d)(\d{{1,2}})\.?\s+({_MONTH_ALT})\.?,?\s+(\d{{4}})(?!\d)", re.IGNORECASE)

# Keyword groups, matched against the text right before (and just after) a date.
_ISSUE_KEYWORDS = (
    "rechnungsdatum", "rechnung vom", "belegdatum", "ausstellungsdatum", "ausgestellt",
    "datum", "date", "invoice date", "bescheid vom", "schreiben vom", "bestätigung vom",
    "gutschrift vom", "angebot vom", "ausgestellt am", "erstellt am", "vom",
)
_DELIVERY_KEYWORDS = (
    "lieferdatum", "leistungsdatum", "leistungszeitpunkt", "lieferung", "liefertermin",
    "bestelldatum", "auftragsdatum", "bestellt am", "versand", "termin",
)
_DUE_KEYWORDS = (
    "fällig", "faellig", "zahlbar bis", "zahlungsziel", "zahlungsfrist", "bis zum",
    "spätestens", "frist", "zahlen sie bis", "due",
)
_PERIOD_KEYWORDS = ("zeitraum", "abrechnungszeitraum", "leistungszeitraum", "von", "bis")
_BIRTH_KEYWORDS = ("geboren", "geb.", "geburtsdatum", "geburtstag", "born", "date of birth")
_PRINT_KEYWORDS = ("druckdatum", "gedruckt", "ausdruck", "printed")

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


def _iter_dates(line: str, today: datetime.date):
    for match in _ISO.finditer(line):
        value = _make_date(int(match[3]), int(match[2]), int(match[1]), today)
        if value:
            yield value, match.span(), match.group(0), "iso"
    for match in _NUMERIC_DE.finditer(line):
        value = _make_date(int(match[1]), int(match[2]), int(match[3]), today)
        if value:
            yield value, match.span(), match.group(0), "de"
    for match in _WORDY.finditer(line):
        month = _MONTHS.get(match[2].lower())
        if month:
            value = _make_date(int(match[1]), month, int(match[3]), today)
            if value:
                yield value, match.span(), match.group(0), "wordy"
    for match in _SLASH.finditer(line):
        value = _make_date(int(match[1]), int(match[2]), int(match[3]), today)
        if value:
            yield value, match.span(), match.group(0), "slash"


def _last_keyword_end(window: str, keywords: tuple[str, ...]) -> int:
    """End index of the last keyword occurrence in ``window`` (-1 if none)."""
    end = -1
    for kw in keywords:
        for match in re.finditer(rf"(?<![a-zäöü]){re.escape(kw)}", window):
            end = max(end, match.end())
    return end


# Ordered by priority for ties; (label, score adjustment, keywords).
_GROUPS: tuple[tuple[str, float, tuple[str, ...]], ...] = (
    ("due", -0.3, _DUE_KEYWORDS),
    ("delivery", -0.1, _DELIVERY_KEYWORDS),
    ("other", -0.15, _PRINT_KEYWORDS),
    ("issue", 0.45, ("rechnungsdatum", "belegdatum", "ausstellungsdatum", "invoice date")),
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
                if kind == "slash":
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

