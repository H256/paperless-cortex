from __future__ import annotations

import json
import math
import re
import time
from hashlib import sha256
from json import JSONDecodeError
from typing import TYPE_CHECKING, Any

import httpx

from app.models import Document, DocumentOcrScore, DocumentPageText
from app.services.runtime.time_utils import utc_now_iso

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

_WEIRD_RE = re.compile(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\u024F\u1E00-\u1EFF]")
_MULTI_SPACE_RE = re.compile(r"[ \t]{3,}")
_REPEAT_RE = re.compile(r"(.)\1{6,}")
_LINE_RE = re.compile(r"\r\n|\r|\n")
_WORD_RE = re.compile(r"\b[^\W\d_]{2,}\b", re.UNICODE)


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def _hash_text(text: str) -> str:
    return sha256((text or "").encode("utf-8")).hexdigest()


def _post_json(settings: Settings, url: str, payload: dict[str, Any], timeout: int) -> tuple[int, Any]:
    client = httpx.Client(timeout=timeout, verify=settings.httpx_verify_tls)
    try:
        response = client.post(url, json=payload)
        try:
            return response.status_code, response.json()
        except (JSONDecodeError, ValueError):
            return response.status_code, response.text
    finally:
        client.close()


def ocr_noise_metrics(text: str) -> dict[str, float]:
    size = len(text)
    if size == 0:
        return {
            "len": 0.0,
            "weird_char_ratio": 1.0,
            "multispace_ratio": 0.0,
            "repeat_run_ratio": 0.0,
            "digit_ratio": 0.0,
            "punct_ratio": 0.0,
            "avg_word_len": 0.0,
            "short_word_ratio": 0.0,
            "line_count": 0.0,
            "avg_line_len": 0.0,
        }

    weird = len(_WEIRD_RE.findall(text))
    multispace = len(_MULTI_SPACE_RE.findall(text))
    repeats = len(_REPEAT_RE.findall(text))
    digits = sum(ch.isdigit() for ch in text)
    punct = sum(ch in r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~""" for ch in text)

    words = _WORD_RE.findall(text)
    avg_word_len = _safe_div(sum(len(w) for w in words), len(words))
    short_words = sum(1 for w in words if len(w) <= 2)
    short_word_ratio = _safe_div(short_words, len(words))

    lines = _LINE_RE.split(text)
    line_count = float(len(lines))
    avg_line_len = _safe_div(sum(len(line) for line in lines), len(lines))

    return {
        "len": float(size),
        "weird_char_ratio": weird / size,
        "multispace_ratio": multispace / max(1.0, size / 200.0),
        "repeat_run_ratio": repeats / max(1.0, size / 50.0),
        "digit_ratio": digits / size,
        "punct_ratio": punct / size,
        "avg_word_len": float(avg_word_len),
        "short_word_ratio": float(short_word_ratio),
        "line_count": float(line_count),
        "avg_line_len": float(avg_line_len),
    }


def heuristic_quality_score(noise: dict[str, float]) -> float:
    weird = min(20.0, noise["weird_char_ratio"] * 400.0)
    repeat = min(15.0, noise["repeat_run_ratio"] * 3.0)
    multispace = min(15.0, noise["multispace_ratio"] * 2.0)
    short_words = min(10.0, noise["short_word_ratio"] * 30.0)
    avg_word_pen = 0.0
    if noise["avg_word_len"] > 10.0:
        avg_word_pen = min(10.0, (noise["avg_word_len"] - 10.0) * 1.5)
    line_pen = 0.0
    if noise["line_count"] > 3 and noise["avg_line_len"] < 25.0:
        line_pen = min(10.0, (25.0 - noise["avg_line_len"]) * 0.4)
    return weird + repeat + multispace + short_words + avg_word_pen + line_pen


def _final_verdict(settings: Settings, score: float) -> str:
    if score >= settings.ocr_score_threshold_bad:
        return "bad"
    if score >= settings.ocr_score_threshold_borderline:
        return "borderline"
    return "good"


def try_prompt_logprob_ppl(settings: Settings, text: str, model: str | None) -> dict[str, Any]:
    if not settings.ocr_score_enable_logprob_ppl:
        return {"supported": False, "reason": "disabled"}
    chat_base_url = settings.ocr_chat_base_url or settings.llm_base_url
    if not chat_base_url:
        return {"supported": False, "reason": "missing chat base url"}
    if not text or len(text) < 50:
        return {"supported": False, "reason": "text too short"}

    text = text[: settings.ocr_score_ppl_max_prompt_chars]
    chunks = [
        text[i : i + settings.ocr_score_ppl_chunk_chars]
        for i in range(0, len(text), settings.ocr_score_ppl_chunk_chars)
    ]

    total_logprob = 0.0
    total_tokens = 0
    started = time.time()
    model_name = model or "default"

    chat_base = chat_base_url.rstrip("/")
    for chunk in chunks:
        payload: dict[str, Any] = {
            "model": model_name,
            "prompt": chunk,
            "max_tokens": 0,
            "echo": True,
            "logprobs": 1,
            "temperature": 0.0,
        }
        status, resp = _post_json(
            settings,
            f"{chat_base}/v1/completions",
            payload,
            timeout=settings.ocr_score_ppl_timeout_seconds,
        )

        if status >= 400 or (isinstance(resp, dict) and "error" in resp):
            payload["max_tokens"] = 1
            payload["stop"] = ["\n\n"]
            status, resp = _post_json(
                settings,
                f"{chat_base}/v1/completions",
                payload,
                timeout=settings.ocr_score_ppl_timeout_seconds,
            )

        if not isinstance(resp, dict):
            return {"supported": False, "reason": f"non-json response ({status})"}

        choices = resp.get("choices")
        if not (isinstance(choices, list) and choices):
            return {"supported": False, "reason": "no choices"}

        logprobs = choices[0].get("logprobs")
        if not isinstance(logprobs, dict):
            return {"supported": False, "reason": "no logprobs field"}

        token_logprobs = logprobs.get("token_logprobs")
        if not (isinstance(token_logprobs, list) and token_logprobs):
            return {"supported": False, "reason": "logprobs not provided by server"}

        values = [val for val in token_logprobs if isinstance(val, (int, float))]
        if not values:
            return {"supported": False, "reason": "token_logprobs empty"}

        total_logprob += float(sum(values))
        total_tokens += len(values)

    avg_logprob = total_logprob / max(1, total_tokens)
    ppl = math.exp(-avg_logprob)
    return {
        "supported": True,
        "ppl": float(ppl),
        "avg_logprob": float(avg_logprob),
        "tokens": int(total_tokens),
        "seconds": float(time.time() - started),
    }


def ppl_quality_penalty(ppl: float) -> float:
    value = math.log(max(1.0, ppl), 2)
    return min(35.0, value * 6.0)


def score_ocr_text(settings: Settings, text: str, model: str | None) -> dict[str, Any]:
    noise = ocr_noise_metrics(text)
    hscore = heuristic_quality_score(noise)
    ppl_res = try_prompt_logprob_ppl(settings, text, model=model)
    ppl_pen = 0.0
    if ppl_res.get("supported"):
        ppl_pen = ppl_quality_penalty(float(ppl_res["ppl"]))
    total = hscore + ppl_pen
    return {
        "verdict": _final_verdict(settings, total),
        "quality_score": total,
        "components": {
            "heuristics": hscore,
            "ppl_penalty": ppl_pen,
        },
        "noise": noise,
        "ppl": ppl_res,
    }


def ensure_document_ocr_score(
    settings: Settings,
    db: Session,
    doc: Document,
    source: str,
    *,
    force: bool = False,
) -> DocumentOcrScore | None:
    source = str(source)
    if source not in ("paperless_ocr", "vision_ocr"):
        return None

    if source == "paperless_ocr":
        text = doc.content or ""
    else:
        pages = (
            db.query(DocumentPageText)
            .filter(DocumentPageText.doc_id == doc.id, DocumentPageText.source == "vision_ocr")
            .order_by(DocumentPageText.page.asc())
            .all()
        )
        if not pages:
            return None
        text = "\n\n".join(page.text or "" for page in pages)

    content_hash = _hash_text(text)
    existing = db.get(DocumentOcrScore, (doc.id, source))
    if existing and not force and existing.content_hash == content_hash:
        return existing

    model_name = settings.ocr_score_model or settings.text_model
    scored = score_ocr_text(settings, text, model=model_name)
    processed_at = utc_now_iso()

    if not existing:
        existing = DocumentOcrScore(doc_id=doc.id, source=source, created_at=processed_at)
        db.add(existing)

    existing.content_hash = content_hash
    existing.quality_score = float(scored["quality_score"])
    existing.verdict = str(scored["verdict"])
    existing.components_json = json.dumps(scored["components"], ensure_ascii=False)
    existing.noise_json = json.dumps(scored["noise"], ensure_ascii=False)
    existing.ppl_json = json.dumps(scored["ppl"], ensure_ascii=False)
    existing.model_name = model_name
    existing.processed_at = processed_at
    db.commit()
    return existing
