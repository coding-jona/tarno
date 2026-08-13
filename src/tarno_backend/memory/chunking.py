"""Text chunking for the TARNO knowledge base (CPU-only).

Tries to preserve Markdown headers and fenced code blocks so that a single
chunk remains semantically coherent and syntactically valid.
"""

from __future__ import annotations

import re
from pathlib import Path


# Separators tried in order of preference.  We split on the *least* harmful
# separator first: Markdown headers, then paragraph, line, word.
_CHUNK_SEPARATORS = [r"\n# ", r"\n## ", r"\n### ", "\n\n", "\n", " "]

# Fence markers for code / verbatim blocks.
_CODE_FENCE = re.compile(r"^```[\s\S]*?^```", re.MULTILINE)


def _split_preserving_fences(text: str) -> list[tuple[str, bool]]:
    """Split *text* into normal and code-fence segments.

    Returns a list of (segment, is_code) tuples.  Code fences are kept
    intact so chunking never cuts them apart.
    """
    parts: list[tuple[str, bool]] = []
    pos = 0
    for match in _CODE_FENCE.finditer(text):
        start, end = match.span()
        if start > pos:
            parts.append((text[pos:start], False))
        parts.append((text[start:end], True))
        pos = end
    if pos < len(text):
        parts.append((text[pos:], False))
    return parts


def _split_text_segment(text: str, separators: list[str], chunk_size: int, overlap: int) -> list[str]:
    """Recursively split a plain-text segment by separators until pieces fit."""
    if len(text) <= chunk_size:
        return [text]

    for sep in separators:
        if sep in text:
            pieces = text.split(sep)
            # Keep the separator with each piece (except the first).
            pieces = [pieces[0]] + [sep + p for p in pieces[1:]]
            chunks: list[str] = []
            current = ""
            for piece in pieces:
                if len(current) + len(piece) <= chunk_size:
                    current += piece
                else:
                    if current:
                        chunks.append(current)
                    if len(piece) > chunk_size:
                        # Piece still too large: recurse with next separator.
                        next_seps = separators[separators.index(sep) + 1 :]
                        if not next_seps:
                            # Last resort: hard split at chunk_size.
                            chunks.extend(_hard_split(piece, chunk_size, overlap))
                        else:
                            chunks.extend(_split_text_segment(piece, next_seps, chunk_size, overlap))
                    else:
                        current = piece
            if current:
                chunks.append(current)
            return _apply_overlap(chunks, chunk_size, overlap)

    # No separators found and too long: hard split.
    return _hard_split(text, chunk_size, overlap)


def _hard_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into fixed-size blocks with overlap as a last resort."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap if chunk_size > overlap else chunk_size
    return chunks


def _apply_overlap(chunks: list[str], chunk_size: int, overlap: int) -> list[str]:
    """Add trailing overlap from the previous chunk to each subsequent chunk."""
    if not chunks or overlap <= 0:
        return chunks
    result = [chunks[0]]
    for chunk in chunks[1:]:
        if len(chunk) + overlap <= chunk_size:
            prev = chunks[len(result) - 1]
            prefix = prev[-overlap:] if len(prev) >= overlap else prev
            chunk = prefix + chunk
        result.append(chunk)
    return result


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    """Return a list of text chunks for the given input.

    Code fences are never split.  Headers/paragraphs are preferred split
    points.  Overlap helps preserve context at chunk boundaries.
    """
    if not text:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        overlap = 0

    parts = _split_preserving_fences(text)
    chunks: list[str] = []
    buffer = ""
    for segment, is_code in parts:
        if is_code:
            # Flush the text buffer before appending an atomic code fence.
            if buffer:
                chunks.extend(_split_text_segment(buffer, _CHUNK_SEPARATORS, chunk_size, overlap))
                buffer = ""
            if len(segment) > chunk_size:
                # Oversized code fence: split line-by-line inside the fence.
                chunks.extend(_split_text_segment(segment, ["\n"], chunk_size, overlap))
            else:
                chunks.append(segment)
        else:
            if buffer:
                # Ensure a clean boundary between prose and code.
                buffer = buffer.rstrip() + "\n\n" + segment
            else:
                buffer = segment
    if buffer:
        chunks.extend(_split_text_segment(buffer, _CHUNK_SEPARATORS, chunk_size, overlap))

    # Clean and drop empty fragments.
    cleaned: list[str] = []
    for c in chunks:
        c = c.strip()
        if c:
            cleaned.append(c)
    return cleaned


def chunk_file(path: Path | str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    """Read a text file and chunk its contents."""
    text = Path(path).read_text(encoding="utf-8")
    return chunk_text(text, chunk_size, overlap)
