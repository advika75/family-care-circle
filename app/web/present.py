"""Formatting helpers for templates. Pure text shaping: NO permission decisions are made here, and nothing here
can add data that the service layer did not already return for the viewer's role."""

from __future__ import annotations


def paragraphs(text: str | None) -> list[str]:
    """Split generated text into paragraphs (blank lines separate them; single line breaks are kept inside one)."""
    blocks, current = [], []
    for line in (text or "").splitlines():
        if line.strip():
            current.append(line.strip())
        elif current:
            blocks.append(" ".join(current))
            current = []
    if current:
        blocks.append(" ".join(current))
    return blocks
