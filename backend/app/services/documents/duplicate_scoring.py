"""OCR-tolerant pair scoring for duplicate detection.

Pure functions only: no DB, no vector store. A pair is scored from four signals
(embedding similarity, character n-gram overlap, hard keys, metadata) so that a
downloaded PDF and a scanned print-out of the same document still match while
serial letters with different amounts/numbers do not.
"""

from __future__ import annotations

import re
import unicodedata
import zlib
from dataclasses import dataclass, field

SHINGLE_SIZE = 5
MAX_TEXT_CHARS = 20_000
MIN_TEXT_CHARS = 40

LEVEL_VERY_LIKELY = "very_likely"
LEVEL_LIKELY = "likely"
LEVEL_CHECK = "check"
LEVELS = (LEVEL_VERY_LIKELY, LEVEL_LIKELY, LEVEL_CHECK)

_THRESHOLD_VERY_LIKELY = 0.90
_THRESHOLD_LIKELY = 0.78
_KEY_CONFLICT_CAP = 0.74

_WEIGHTS = {"embedding": 0.35, "text": 0.40, "keys": 0.15, "meta": 0.10}

_NON_ALNUM = re.compile(r"[^0-9a-z]+")
_AMOUNT = re.compile(r"(?<!\d)\d{1,3}(?:[. ]\d{3})*,\d{2}(?!\d)")
_IDENT = re.compile(r"(?<![0-9a-z])(?=[0-9a-z/-]*\d)[0-9a-z][0-9a-z/-]{5,}(?![0-9a-z])")


def normalize_text(text: str | None) -> str:
    """Casefold, strip accents/punctuation and collapse whitespace."""
    if not text:
        return ""
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = folded.replace("ß", "ss")
    return _NON_ALNUM.sub(" ", folded).strip()


def shingle_set(text: str | None, *, size: int = SHINGLE_SIZE) -> frozenset[int]:
    """Hashed character n-grams of the normalized text (spaces removed)."""
    compact = normalize_text(text).replace(" ", "")[:MAX_TEXT_CHARS]
    if len(compact) < max(size, MIN_TEXT_CHARS):
        return frozenset()
    return frozenset(
        zlib.crc32(compact[i : i + size].encode()) for i in range(len(compact) - size + 1)
    )


def jaccard(left: frozenset[int] | set[str], right: frozenset[int] | set[str]) -> float | None:
    if not left or not right:
        return None
    union = len(left | right)
    return len(left & right) / union if union else None


def extract_amounts(text: str | None) -> frozenset[str]:
    if not text:
        return frozenset()
    return frozenset(re.sub(r"[. ]", "", match) for match in _AMOUNT.findall(text))


def extract_identifiers(text: str | None) -> frozenset[str]:
    if not text:
        return frozenset()
    # Mostly-digit tokens only: OCR junk like "innerha1b" must not become a key.
    return frozenset(
        token
        for token in _IDENT.findall(text.casefold())
        if (digits := sum(ch.isdigit() for ch in token)) >= 4 and digits * 2 >= len(token)
    )


@dataclass(frozen=True)
class DocFingerprint:
    doc_id: int
    shingles: frozenset[int] = frozenset()
    amounts: frozenset[str] = frozenset()
    identifiers: frozenset[str] = frozenset()
    correspondent_id: int | None = None
    document_type_id: int | None = None
    document_date: str | None = None
    page_count: int | None = None


def fingerprint_from_text(
    doc_id: int,
    text: str | None,
    *,
    correspondent_id: int | None = None,
    document_type_id: int | None = None,
    document_date: str | None = None,
    page_count: int | None = None,
) -> DocFingerprint:
    return DocFingerprint(
        doc_id=int(doc_id),
        shingles=shingle_set(text),
        amounts=extract_amounts(text),
        identifiers=extract_identifiers(text),
        correspondent_id=correspondent_id,
        document_type_id=document_type_id,
        document_date=document_date or None,
        page_count=page_count,
    )


@dataclass(frozen=True)
class PairScore:
    score: float
    level: str
    embedding_score: float | None
    text_score: float | None
    keys_score: float | None
    meta_score: float | None
    signals: dict[str, object] = field(default_factory=dict)


def _keys_score(left: DocFingerprint, right: DocFingerprint) -> tuple[float | None, bool]:
    """Return (score, conflict). Conflict = both sides carry keys but share none."""
    scores: list[float] = []
    conflict = False
    for a, b in ((left.amounts, right.amounts), (left.identifiers, right.identifiers)):
        if not a or not b:
            continue
        # Overlap coefficient: stray OCR tokens on one side must not dilute a real match.
        value = len(a & b) / min(len(a), len(b))
        scores.append(value)
        if value == 0.0:
            conflict = True
    if not scores:
        return None, False
    return sum(scores) / len(scores), conflict


def _meta_score(left: DocFingerprint, right: DocFingerprint) -> tuple[float | None, dict[str, bool]]:
    checks: dict[str, bool] = {}
    if left.correspondent_id is not None and right.correspondent_id is not None:
        checks["correspondent"] = left.correspondent_id == right.correspondent_id
    if left.document_type_id is not None and right.document_type_id is not None:
        checks["document_type"] = left.document_type_id == right.document_type_id
    if left.document_date and right.document_date:
        checks["document_date"] = left.document_date == right.document_date
    if left.page_count and right.page_count:
        checks["page_count"] = left.page_count == right.page_count
    if not checks:
        return None, checks
    return sum(1 for ok in checks.values() if ok) / len(checks), checks


def level_for_score(score: float) -> str:
    if score >= _THRESHOLD_VERY_LIKELY:
        return LEVEL_VERY_LIKELY
    if score >= _THRESHOLD_LIKELY:
        return LEVEL_LIKELY
    return LEVEL_CHECK


def score_pair(
    left: DocFingerprint,
    right: DocFingerprint,
    *,
    embedding_score: float | None,
) -> PairScore:
    text_score = jaccard(left.shingles, right.shingles)
    keys_score, key_conflict = _keys_score(left, right)
    meta_score, meta_checks = _meta_score(left, right)

    parts = {
        "embedding": embedding_score,
        "text": text_score,
        "keys": keys_score,
        "meta": meta_score,
    }
    available = {name: value for name, value in parts.items() if value is not None}
    weight_sum = sum(_WEIGHTS[name] for name in available)
    score = (
        sum(_WEIGHTS[name] * float(value) for name, value in available.items()) / weight_sum
        if weight_sum
        else 0.0
    )
    if key_conflict:
        score = min(score, _KEY_CONFLICT_CAP)
    score = round(max(0.0, min(1.0, score)), 4)
    return PairScore(
        score=score,
        level=level_for_score(score),
        embedding_score=embedding_score,
        text_score=text_score,
        keys_score=keys_score,
        meta_score=meta_score,
        signals={
            "key_conflict": key_conflict,
            "meta": meta_checks,
            "shared_amounts": sorted(left.amounts & right.amounts),
            "shared_identifiers": sorted(left.identifiers & right.identifiers),
        },
    )


def cluster_pairs(pairs: list[tuple[int, int]]) -> list[list[int]]:
    """Union-find over pair edges; returns groups of >= 2 doc ids, sorted."""
    parent: dict[int, int] = {}

    def find(node: int) -> int:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for left, right in pairs:
        root_l, root_r = find(int(left)), find(int(right))
        if root_l != root_r:
            parent[max(root_l, root_r)] = min(root_l, root_r)
    groups: dict[int, list[int]] = {}
    for node in list(parent):
        groups.setdefault(find(node), []).append(node)
    return sorted((sorted(members) for members in groups.values() if len(members) > 1), key=lambda g: g[0])
