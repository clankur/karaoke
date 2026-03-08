"""Text utilities for handling CJK and multi-script karaoke text."""


def is_cjk_char(char: str) -> bool:
    """Check if a character is in a CJK Unicode range.

    Covers CJK Unified Ideographs, Hiragana, Katakana, Hangul Syllables,
    and related ranges. Does NOT include space-delimited scripts like
    Devanagari, Cyrillic, or Arabic — those work fine with whitespace splitting.
    """
    cp = ord(char)
    return (
        (0x4E00 <= cp <= 0x9FFF)        # CJK Unified Ideographs
        or (0x3400 <= cp <= 0x4DBF)     # CJK Extension A
        or (0x3040 <= cp <= 0x309F)     # Hiragana
        or (0x30A0 <= cp <= 0x30FF)     # Katakana
        or (0xAC00 <= cp <= 0xD7AF)     # Hangul Syllables
        or (0x1100 <= cp <= 0x11FF)     # Hangul Jamo
        or (0xF900 <= cp <= 0xFAFF)     # CJK Compatibility Ideographs
        or (0x20000 <= cp <= 0x2A6DF)   # CJK Extension B
    )


def tokenize_for_karaoke(text: str) -> list[str]:
    """Split text into tokens suitable for karaoke timing.

    For space-delimited languages (Latin, Devanagari, Cyrillic, Arabic, etc.),
    splits on whitespace. For CJK text, each character becomes its own token
    so karaoke highlighting can progress character by character.

    Mixed text (e.g. "Hello こんにちは World") is handled correctly: Latin words
    are kept together, CJK characters are split individually.
    """
    tokens: list[str] = []
    current: list[str] = []

    for char in text:
        if is_cjk_char(char):
            # Flush any accumulated non-CJK text
            if current:
                word = "".join(current).strip()
                if word:
                    tokens.extend(word.split())
                current = []
            tokens.append(char)
        elif char.isspace():
            if current:
                word = "".join(current).strip()
                if word:
                    tokens.extend(word.split())
                current = []
        else:
            current.append(char)

    # Flush remaining
    if current:
        word = "".join(current).strip()
        if word:
            tokens.extend(word.split())

    return tokens
