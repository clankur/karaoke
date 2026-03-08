"""End-to-end tests for the non-English karaoke pipeline.

These tests exercise real internal code paths — lyrics parsing, title cleaning,
alignment fallback with CJK tokenization, and ASS subtitle generation — while
mocking only external boundaries (syncedlyrics, stable_whisper, ffmpeg/demucs).
"""

from unittest.mock import MagicMock, patch

from karaoke.align import _lang_kwargs, align
from karaoke.lyrics import fetch_lyrics
from karaoke.render import _generate_ass, _select_font


# --- Controlled LRC data for tests ---

HINDI_LRC = (
    "[00:10.00] Balam pichkari jo tune mujhe maari\n"
    "[00:15.00] Toh seedhi saadi chhori sharabi ho gayi\n"
    "[00:20.00] Holi khelne hum aaye hain\n"
)

JAPANESE_LRC = (
    "[00:05.00] 残酷な天使のように\n"
    "[00:10.00] 少年よ神話になれ\n"
    "[00:15.00] 蒼い風がいま\n"
)


class TestE2EHindiPipeline:
    """E2E test: Hindi video with noisy title, track metadata, and synced LRC lyrics.

    Real code exercised:
    - fetch_lyrics → _clean_title → _search_lyrics → _parse_lrc
    - align → whisper fallback → _lines_from_synced → tokenize_for_karaoke → _distribute_word_timing
    - _select_font → _generate_ass → _build_karaoke_text
    """

    def test_e2e_hindi_pipeline(self, tmp_path):
        # --- Stage 1: Lyrics fetch (mock syncedlyrics, real parsing) ---
        with patch("karaoke.lyrics.syncedlyrics.search", return_value=HINDI_LRC) as mock_search:
            lyrics = fetch_lyrics("Balam Pichkari", artist="Vishal Dadlani")

        # Should search with "title artist" first
        first_query = mock_search.call_args_list[0][0][0]
        assert "Balam Pichkari" in first_query
        assert "Vishal Dadlani" in first_query

        # Real _parse_lrc produced synced lines
        assert lyrics is not None
        assert lyrics.has_synced_timestamps
        assert len(lyrics.synced_lines) == 3
        assert lyrics.synced_lines[0].timestamp == 10.0
        assert "Balam pichkari" in lyrics.synced_lines[0].text

        # --- Stage 2: Alignment (mock whisper, real fallback path) ---
        vocals_path = tmp_path / "vocals.wav"
        vocals_path.write_bytes(b"\x00" * 100)

        mock_model = MagicMock()
        mock_model.align.side_effect = Exception("forced fallback for testing")

        with patch("karaoke.align.stable_whisper.load_model", return_value=mock_model):
            alignment = align(vocals_path, lyrics=lyrics, language="hi")

        # Real _lines_from_synced + tokenize_for_karaoke produced timed lines
        assert len(alignment.lines) > 0

        # Hindi is space-delimited, so words should be split by whitespace
        # First LRC line: "Balam pichkari jo tune mujhe maari" = 6 words
        first_line_words = alignment.lines[0].words
        first_line_text = [w.text for w in first_line_words]
        assert "Balam" in first_line_text
        assert "pichkari" in first_line_text

        # All words should have valid timing
        for line in alignment.lines:
            for word in line.words:
                assert word.start < word.end, f"Bad timing for '{word.text}'"

        # --- Stage 3: ASS generation (real font selection + subtitle rendering) ---
        ass_path = tmp_path / "output.ass"
        font = _select_font("hi")
        assert font == "Noto Sans"  # Hindi → non-Latin font

        _generate_ass(alignment, ass_path, font_name=font)
        ass_content = ass_path.read_text()

        # Verify ASS structure
        assert "Noto Sans" in ass_content
        assert "\\kf" in ass_content
        assert "Dialogue:" in ass_content
        assert "[V4+ Styles]" in ass_content

    def test_e2e_hindi_title_cleaning_retry(self, tmp_path):
        """Verify title cleaning and retry logic for noisy Bollywood titles."""
        noisy_title = (
            "Balam Pichkari (Full Video) | Yeh Jawaani Hai Deewani | "
            "Pritam | Ranbir Kapoor, Deepika | Holi Song"
        )

        call_count = 0

        def mock_search(query):
            nonlocal call_count
            call_count += 1
            # Fail on noisy queries, succeed on clean "Balam Pichkari"
            if query == "Balam Pichkari":
                return HINDI_LRC
            return None

        with patch("karaoke.lyrics.syncedlyrics.search", side_effect=mock_search):
            lyrics = fetch_lyrics(noisy_title)

        # Should have retried with cleaned variants and eventually found lyrics
        assert lyrics is not None
        assert lyrics.has_synced_timestamps
        assert call_count >= 2  # At least one failed query + the successful one


class TestE2EJapanesePipeline:
    """E2E test: Japanese video with CJK text, character-level tokenization.

    Real code exercised:
    - fetch_lyrics → _clean_title strips "(Official Video)" → _parse_lrc
    - align → whisper fallback → tokenize_for_karaoke (CJK char-level split)
    - _generate_ass with Noto Sans CJK, no spaces between CJK characters
    """

    def test_e2e_japanese_pipeline(self, tmp_path):
        # --- Stage 1: Lyrics fetch with title cleaning ---
        noisy_title = "残酷な天使のテーゼ (Official Video)"

        with patch("karaoke.lyrics.syncedlyrics.search", return_value=JAPANESE_LRC) as mock_search:
            lyrics = fetch_lyrics(noisy_title)

        assert lyrics is not None
        assert lyrics.has_synced_timestamps
        assert len(lyrics.synced_lines) == 3

        # Title cleaning should have stripped "(Official Video)"
        queries = [call[0][0] for call in mock_search.call_args_list]
        # At least one query should be the cleaned title
        assert any("残酷な天使のテーゼ" in q and "(Official Video)" not in q for q in queries)

        # --- Stage 2: Alignment with CJK character-level tokenization ---
        vocals_path = tmp_path / "vocals.wav"
        vocals_path.write_bytes(b"\x00" * 100)

        mock_model = MagicMock()
        mock_model.align.side_effect = Exception("forced fallback for testing")

        with patch("karaoke.align.stable_whisper.load_model", return_value=mock_model):
            alignment = align(vocals_path, lyrics=lyrics, language="ja")

        # CJK characters should be individually tokenized
        assert len(alignment.lines) > 0
        # First LRC line: "残酷な天使のように" = 8 CJK characters = 8 tokens
        # With words_per_line=7, this should produce 2 lines from the first LRC line
        all_words_line1 = []
        # Collect words from the first LRC line's time range
        for line in alignment.lines:
            if line.words and line.words[0].start >= 5.0 and line.words[0].start < 10.0:
                all_words_line1.extend(line.words)

        cjk_chars = [w.text for w in all_words_line1]
        # Each CJK character should be its own token
        assert "残" in cjk_chars
        assert "酷" in cjk_chars
        assert "な" in cjk_chars

        # --- Stage 3: ASS generation with CJK font and spacing ---
        ass_path = tmp_path / "output.ass"
        font = _select_font("ja")
        assert font == "Noto Sans CJK"

        _generate_ass(alignment, ass_path, font_name=font)
        ass_content = ass_path.read_text()

        # Verify CJK font in ASS
        assert "Noto Sans CJK" in ass_content
        assert "\\kf" in ass_content

        # Verify no spaces between adjacent CJK karaoke tags
        # Pattern: "}残{\kf" (no space between CJK char and next tag)
        dialogue_lines = [l for l in ass_content.splitlines() if l.startswith("Dialogue:")]
        assert len(dialogue_lines) > 0
        for dline in dialogue_lines:
            # Extract the text portion after the last comma
            text_part = dline.split(",", 9)[-1]
            # Between adjacent CJK chars, there should be no space
            # e.g. "{\kf10}残{\kf10}酷" not "{\kf10}残 {\kf10}酷"
            import re
            # Find all sequences of "CJK_char space {\kf" — these should NOT exist
            cjk_space_pattern = re.compile(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff] \\kf")
            assert not cjk_space_pattern.search(text_part), (
                f"Found space between CJK characters in ASS: {text_part}"
            )


class TestLangKwargs:
    """Regression tests for the language=None crash with stable_whisper."""

    def test_lang_kwargs_omits_none(self):
        """_lang_kwargs(None) must return {} to avoid TypeError in stable_whisper."""
        result = _lang_kwargs(None)
        assert result == {}
        assert "language" not in result

    def test_lang_kwargs_includes_value(self):
        assert _lang_kwargs("hi") == {"language": "hi"}
        assert _lang_kwargs("ja") == {"language": "ja"}
        assert _lang_kwargs("en") == {"language": "en"}

    def test_align_with_none_language_does_not_pass_language_kwarg(self, tmp_path):
        """Ensure align() doesn't pass language=None to stable_whisper model."""
        vocals_path = tmp_path / "vocals.wav"
        vocals_path.write_bytes(b"\x00" * 100)

        mock_model = MagicMock()
        # Make align raise to test what kwargs were passed
        mock_model.align.side_effect = Exception("test")
        mock_model.transcribe.side_effect = Exception("test")

        with patch("karaoke.align.stable_whisper.load_model", return_value=mock_model):
            # With plain text lyrics (no synced) and language=None
            from karaoke.models import LyricsResult

            lyrics = LyricsResult(plain_text="hello world")
            try:
                align(vocals_path, lyrics=lyrics, language=None)
            except RuntimeError:
                pass

        # model.align was called — check it did NOT receive language=None
        if mock_model.align.called:
            kwargs = mock_model.align.call_args.kwargs
            assert "language" not in kwargs, (
                f"language=None was passed to model.align: {kwargs}"
            )
