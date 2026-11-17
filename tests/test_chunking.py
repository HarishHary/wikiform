from __future__ import annotations

from wikiform.utils.chunking import chunk_text


def test_short_text_is_single_chunk():
    assert chunk_text("hello world") == ["hello world"]


def test_empty_text_returns_one_chunk():
    assert chunk_text("") == [""]


def test_long_text_split_on_paragraphs_within_limit():
    text = "\n\n".join(f"paragraph {i} " + "word " * 40 for i in range(20))
    chunks = chunk_text(text, max_chars=500)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)
    assert "paragraph 0" in chunks[0] and "paragraph 19" in chunks[-1]


def test_oversized_paragraph_is_split_on_whitespace():
    chunks = chunk_text("word " * 1000, max_chars=200)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)


def test_unbroken_token_is_hard_split():
    chunks = chunk_text("x" * 1000, max_chars=300)
    assert all(len(c) <= 300 for c in chunks)
    assert "".join(chunks) == "x" * 1000
