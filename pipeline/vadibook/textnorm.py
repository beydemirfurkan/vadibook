"""Turkish-aware normalisation for search fields.

Python's str.lower() turns "İ" into "i̇" (i + combining dot) and "I" into "i"; both are
wrong for Turkish. We map the two capitals first, then lower the rest.
"""

_TR_CAPITALS = str.maketrans({"I": "ı", "İ": "i"})
_CIRCUMFLEX = str.maketrans({"â": "a", "î": "i", "û": "u"})
_ASCII_FOLD = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u"})


def normalize_tr(text: str) -> str:
    """Lowercase with Turkish i/ı rules and strip circumflexes (kâr -> kar)."""
    return text.translate(_TR_CAPITALS).lower().translate(_CIRCUMFLEX)


def to_ascii(text: str) -> str:
    """normalize_tr + fold Turkish letters to ASCII so 'kasifoglu' matches 'Kaşifoğlu'."""
    return normalize_tr(text).translate(_ASCII_FOLD)
