"""Tests for brainpack.transcriber — Whisper backend selection and transcription."""
import pytest
from unittest.mock import patch, MagicMock, call
from pathlib import Path

from brainpack.transcriber import transcribe_audio, _is_apple_silicon


# TRN-01: Backend selection
class TestBackendSelection:
    def test_apple_silicon_uses_mlx(self, tmp_path):
        """arm64 + darwin → mlx-whisper called."""
        audio = tmp_path / "test.m4a"
        audio.write_bytes(b"x" * 100_000)
        with patch("brainpack.transcriber._is_apple_silicon", return_value=True), \
             patch("brainpack.transcriber._transcribe_mlx", return_value=[]) as mock_mlx:
            transcribe_audio(audio, model_size="small")
        mock_mlx.assert_called_once()

    def test_non_apple_silicon_uses_faster_whisper(self, tmp_path):
        """Non-arm64 or non-darwin → faster-whisper called."""
        audio = tmp_path / "test.m4a"
        audio.write_bytes(b"x" * 100_000)
        with patch("brainpack.transcriber._is_apple_silicon", return_value=False), \
             patch("brainpack.transcriber._transcribe_faster", return_value=[]) as mock_fw:
            transcribe_audio(audio, model_size="small")
        mock_fw.assert_called_once()

    def test_is_apple_silicon_returns_bool(self):
        """_is_apple_silicon returns a bool regardless of platform."""
        result = _is_apple_silicon()
        assert isinstance(result, bool)

    def test_transcribe_audio_returns_empty_list_on_exception(self, tmp_path):
        """transcribe_audio returns [] when backend raises — never propagates."""
        audio = tmp_path / "test.m4a"
        audio.write_bytes(b"x" * 100_000)
        with patch("brainpack.transcriber._is_apple_silicon", return_value=False), \
             patch("brainpack.transcriber._transcribe_faster", side_effect=RuntimeError("backend error")):
            result = transcribe_audio(audio, model_size="small")
        assert result == []

    def test_language_passed_to_mlx_backend(self, tmp_path):
        """language='tr' is passed through to mlx backend."""
        audio = tmp_path / "test.m4a"
        audio.write_bytes(b"x" * 100_000)
        with patch("brainpack.transcriber._is_apple_silicon", return_value=True), \
             patch("brainpack.transcriber._transcribe_mlx", return_value=[]) as mock_mlx:
            transcribe_audio(audio, model_size="small", language="tr")
        mock_mlx.assert_called_once_with(audio, "small", "tr")

    def test_language_passed_to_faster_backend(self, tmp_path):
        """language='tr' is passed through to faster-whisper backend."""
        audio = tmp_path / "test.m4a"
        audio.write_bytes(b"x" * 100_000)
        with patch("brainpack.transcriber._is_apple_silicon", return_value=False), \
             patch("brainpack.transcriber._transcribe_faster", return_value=[]) as mock_fw:
            transcribe_audio(audio, model_size="small", language="tr")
        mock_fw.assert_called_once_with(audio, "small", "tr")


# TRN-02: VAD behavior
class TestVADBehavior:
    def test_faster_whisper_called_with_vad_filter_true(self, tmp_path):
        """faster-whisper transcription uses vad_filter=True."""
        audio = tmp_path / "test.m4a"
        audio.write_bytes(b"x" * 100_000)
        mock_fw = MagicMock()
        mock_model = MagicMock()
        mock_fw.WhisperModel.return_value = mock_model
        mock_model.transcribe.return_value = (iter([]), MagicMock())
        with patch.dict("sys.modules", {"faster_whisper": mock_fw}):
            from brainpack.transcriber import _transcribe_faster
            _transcribe_faster(audio, "small", None)
        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs.get("vad_filter") is True
        assert call_kwargs.get("condition_on_previous_text") is False

    def test_mlx_whisper_called_with_condition_on_previous_text_false(self, tmp_path):
        """mlx-whisper uses condition_on_previous_text=False (VAD mitigation)."""
        audio = tmp_path / "test.m4a"
        audio.write_bytes(b"x" * 100_000)
        mock_mlx = MagicMock()
        mock_mlx.transcribe.return_value = {"segments": []}
        with patch.dict("sys.modules", {"mlx_whisper": mock_mlx}):
            from brainpack.transcriber import _transcribe_mlx
            _transcribe_mlx(audio, "small", None)
        call_kwargs = mock_mlx.transcribe.call_args[1]
        assert call_kwargs.get("condition_on_previous_text") is False


# TRN-03: Model size passthrough
class TestModelSize:
    def test_model_size_passed_to_faster_whisper(self, tmp_path):
        """--model medium passes 'medium' to WhisperModel constructor."""
        audio = tmp_path / "test.m4a"
        audio.write_bytes(b"x" * 100_000)
        mock_fw = MagicMock()
        mock_model = MagicMock()
        mock_fw.WhisperModel.return_value = mock_model
        mock_model.transcribe.return_value = (iter([]), MagicMock())
        with patch.dict("sys.modules", {"faster_whisper": mock_fw}):
            from brainpack.transcriber import _transcribe_faster
            _transcribe_faster(audio, "medium", None)
        mock_fw.WhisperModel.assert_called_once_with("medium", device="cpu", compute_type="int8")

    def test_model_size_passed_to_mlx_whisper(self, tmp_path):
        """model_size='base' maps to mlx-community/whisper-base-mlx HF repo."""
        audio = tmp_path / "test.m4a"
        audio.write_bytes(b"x" * 100_000)
        mock_mlx = MagicMock()
        mock_mlx.transcribe.return_value = {"segments": []}
        with patch.dict("sys.modules", {"mlx_whisper": mock_mlx}):
            from brainpack.transcriber import _transcribe_mlx
            _transcribe_mlx(audio, "base", None)
        call_kwargs = mock_mlx.transcribe.call_args[1]
        assert "whisper-base-mlx" in call_kwargs.get("path_or_hf_repo", "")


# TRN-04: Segment timestamps
class TestSegmentTimestamps:
    def test_faster_whisper_segments_have_timestamps(self, tmp_path):
        """faster-whisper output contains start/end timestamps per segment."""
        audio = tmp_path / "test.m4a"
        audio.write_bytes(b"x" * 100_000)
        mock_seg = MagicMock()
        mock_seg.start = 0.0
        mock_seg.end = 5.5
        mock_seg.text = "Hello world"
        mock_fw = MagicMock()
        mock_model = MagicMock()
        mock_fw.WhisperModel.return_value = mock_model
        mock_model.transcribe.return_value = (iter([mock_seg]), MagicMock())
        with patch.dict("sys.modules", {"faster_whisper": mock_fw}):
            from brainpack.transcriber import _transcribe_faster
            result = _transcribe_faster(audio, "small", None)
        assert len(result) == 1
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 5.5
        assert result[0]["text"] == "Hello world"

    def test_mlx_whisper_segments_have_timestamps(self, tmp_path):
        """mlx-whisper output preserves start/end from result['segments']."""
        audio = tmp_path / "test.m4a"
        audio.write_bytes(b"x" * 100_000)
        mock_mlx = MagicMock()
        mock_mlx.transcribe.return_value = {
            "segments": [{"start": 1.0, "end": 3.5, "text": " Merhaba dünya"}]
        }
        with patch.dict("sys.modules", {"mlx_whisper": mock_mlx}):
            from brainpack.transcriber import _transcribe_mlx
            result = _transcribe_mlx(audio, "small", None)
        assert len(result) == 1
        assert result[0]["start"] == 1.0
        assert result[0]["end"] == 3.5
        assert result[0]["text"] == "Merhaba dünya"
