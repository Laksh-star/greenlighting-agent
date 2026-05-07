"""Source material helpers for treatment/script-aware analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


MAX_EXCERPT_CHARS = 6000


def load_source_material(path: Path) -> Dict[str, Any]:
    """Load plain text or Markdown source material from disk."""
    resolved = Path(path)
    text = resolved.read_text()
    return build_source_material_payload(text, name=resolved.name)


def build_source_material_payload(text: str, name: str = "source material") -> Dict[str, Any]:
    """Create a compact, reportable source-material payload."""
    clean_text = normalize_source_text(text)
    words = clean_text.split()
    return {
        "name": name or "source material",
        "text": clean_text,
        "excerpt": clean_text[:MAX_EXCERPT_CHARS],
        "word_count": len(words),
        "character_count": len(clean_text),
        "line_count": len([line for line in clean_text.splitlines() if line.strip()]),
    }


def normalize_source_text(text: str) -> str:
    """Normalize pasted/uploaded text without changing its meaning."""
    lines = [line.rstrip() for line in (text or "").replace("\r\n", "\n").split("\n")]
    compact_lines = []
    blank_seen = False
    for line in lines:
        if not line.strip():
            if not blank_seen:
                compact_lines.append("")
            blank_seen = True
            continue
        compact_lines.append(line)
        blank_seen = False
    return "\n".join(compact_lines).strip()
