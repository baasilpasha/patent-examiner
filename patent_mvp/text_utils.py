from __future__ import annotations

import html
import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")
_SOFT_HYPHEN_WRAP_RE = re.compile(r"(\w)-\s*\n\s*(\w)")


def clean_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = html.unescape(text)
    text = _SOFT_HYPHEN_WRAP_RE.sub(r"\1\2", text)
    text = text.replace("\u00ad", "")
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def chunk_paragraph(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            split = text.rfind(" ", start + 1, end)
            if split > start + max_chars // 2:
                end = split
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(0, end - overlap)
    return [c for c in chunks if c]
