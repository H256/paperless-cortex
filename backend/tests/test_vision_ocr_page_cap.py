from __future__ import annotations

from typing import Any

from app.config import load_settings
from app.services.ai import vision_ocr


def _make_settings(monkeypatch: Any, **overrides: Any) -> Any:
    monkeypatch.setenv("VISION_MODEL", "test-vision")
    monkeypatch.setenv("OCR_VISION_BASE", "http://vision.local")
    for key, value in overrides.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, str(value))
    return load_settings()


def _fake_pages(n: int) -> list[Any]:
    return [
        vision_ocr.VisionPage(
            page_index=i,
            image_bytes=b"png",
            width=100,
            height=100,
        )
        for i in range(n)
    ]


def test_default_page_cap_is_50(monkeypatch: Any) -> None:
    monkeypatch.delenv("VISION_OCR_MAX_PAGES", raising=False)
    settings = _make_settings(monkeypatch)
    assert settings.vision_ocr_max_pages == 50


def test_explicit_zero_page_cap_stays_unlimited(monkeypatch: Any) -> None:
    settings = _make_settings(monkeypatch, VISION_OCR_MAX_PAGES=0)
    assert settings.vision_ocr_max_pages == 0


def test_ocr_pdf_pages_stops_at_cap(monkeypatch: Any) -> None:
    settings = _make_settings(monkeypatch, VISION_OCR_MAX_PAGES=2)
    processed: list[int] = []

    def fake_iter(_pdf: bytes, _nums: Any, **_kw: Any) -> Any:
        return _fake_pages(10)

    def fake_generate(_s: Any, _m: str, _p: str, _img: bytes, **kw: Any) -> str:
        processed.append(kw["page_number"])
        return "text"

    monkeypatch.setattr(vision_ocr, "iter_pdf_pages", fake_iter)
    monkeypatch.setattr(vision_ocr, "_vision_generate", fake_generate)

    results = vision_ocr.ocr_pdf_pages(settings, b"pdf")

    assert [p.page for p in results] == [1, 2]
    assert processed == [1, 2]


def test_ocr_pdf_pages_unlimited_when_cap_zero(monkeypatch: Any) -> None:
    settings = _make_settings(monkeypatch, VISION_OCR_MAX_PAGES=0)

    def fake_iter(_pdf: bytes, _nums: Any, **_kw: Any) -> Any:
        return _fake_pages(3)

    def fake_generate(_s: Any, _m: str, _p: str, _img: bytes, **kw: Any) -> str:
        return "text"

    monkeypatch.setattr(vision_ocr, "iter_pdf_pages", fake_iter)
    monkeypatch.setattr(vision_ocr, "_vision_generate", fake_generate)

    results = vision_ocr.ocr_pdf_pages(settings, b"pdf")
    assert [p.page for p in results] == [1, 2, 3]
