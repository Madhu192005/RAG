"""Conservative text normalization; meaningful source wording is retained."""

import re
import unicodedata


_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HORIZONTAL_SPACE = re.compile(r"[^\S\r\n]+")
_MANY_NEWLINES = re.compile(r"\n{3,}")
_SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([,.;:!?])")


def clean_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    normalized = _CONTROL_CHARS.sub("", normalized)
    lines = [_HORIZONTAL_SPACE.sub(" ", line).strip() for line in normalized.split("\n")]
    normalized = _SPACE_BEFORE_PUNCTUATION.sub(r"\1", "\n".join(lines))
    return _MANY_NEWLINES.sub("\n\n", normalized).strip()
