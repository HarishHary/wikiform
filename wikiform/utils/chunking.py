from __future__ import annotations

import re

# ~1800 chars is roughly 400-450 tokens: safely under the 512-token limit of BGE-style models.
DEFAULT_MAX_CHARS = 1800


def chunk_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    """Split text into chunks of at most *max_chars*, packing whole paragraphs where possible.

    Paragraphs longer than *max_chars* are split on whitespace. Always returns at least one chunk.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        for piece in _split_long(paragraph, max_chars):
            if current and len(current) + len(piece) + 2 > max_chars:
                flush()
            current = f"{current}\n\n{piece}" if current else piece
    flush()
    return chunks or [text[:max_chars]]


def _split_long(paragraph: str, max_chars: int) -> list[str]:
    if len(paragraph) <= max_chars:
        return [paragraph]
    pieces: list[str] = []
    current = ""
    for word in paragraph.split():
        while len(word) > max_chars:  # e.g. a huge unbroken token
            if current:
                pieces.append(current)
                current = ""
            pieces.append(word[:max_chars])
            word = word[max_chars:]
        if current and len(current) + len(word) + 1 > max_chars:
            pieces.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        pieces.append(current)
    return pieces
