"""Tests for the text utilities module."""

from karaoke.text_utils import is_cjk_char, tokenize_for_karaoke


class TestIsCjkChar:
    def test_hiragana(self):
        assert is_cjk_char("あ") is True
        assert is_cjk_char("ん") is True

    def test_katakana(self):
        assert is_cjk_char("ア") is True
        assert is_cjk_char("ン") is True

    def test_kanji(self):
        assert is_cjk_char("漢") is True
        assert is_cjk_char("字") is True

    def test_hangul(self):
        assert is_cjk_char("한") is True
        assert is_cjk_char("글") is True

    def test_latin_returns_false(self):
        assert is_cjk_char("A") is False
        assert is_cjk_char("z") is False
        assert is_cjk_char("1") is False

    def test_devanagari_returns_false(self):
        """Devanagari (Hindi) is space-delimited, not CJK."""
        assert is_cjk_char("न") is False
        assert is_cjk_char("म") is False

    def test_space_returns_false(self):
        assert is_cjk_char(" ") is False

    def test_punctuation_returns_false(self):
        assert is_cjk_char("!") is False
        assert is_cjk_char(".") is False


class TestTokenizeForKaraoke:
    def test_english_text(self):
        assert tokenize_for_karaoke("Hello world") == ["Hello", "world"]

    def test_japanese_text(self):
        result = tokenize_for_karaoke("こんにちは世界")
        assert result == ["こ", "ん", "に", "ち", "は", "世", "界"]

    def test_korean_text(self):
        result = tokenize_for_karaoke("안녕하세요")
        assert result == ["안", "녕", "하", "세", "요"]

    def test_mixed_english_and_japanese(self):
        result = tokenize_for_karaoke("Hello こんにちは World")
        assert result == ["Hello", "こ", "ん", "に", "ち", "は", "World"]

    def test_empty_string(self):
        assert tokenize_for_karaoke("") == []

    def test_whitespace_only(self):
        assert tokenize_for_karaoke("   ") == []

    def test_single_english_word(self):
        assert tokenize_for_karaoke("hello") == ["hello"]

    def test_single_cjk_char(self):
        assert tokenize_for_karaoke("漢") == ["漢"]

    def test_hindi_text_splits_on_spaces(self):
        """Hindi (Devanagari) is space-delimited and should split on spaces."""
        result = tokenize_for_karaoke("नमस्ते दुनिया")
        assert result == ["नमस्ते", "दुनिया"]

    def test_multiple_spaces(self):
        result = tokenize_for_karaoke("hello   world")
        assert result == ["hello", "world"]
