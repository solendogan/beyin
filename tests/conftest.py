"""Shared test fixtures for brainpack tests.

Note: punkt_tab NLTK data must be downloaded once before running tests.
Run: uv run python -c "import nltk; nltk.download('punkt_tab', quiet=True)"
"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Shared CLI test helpers (moved from test_cli.py)
# ---------------------------------------------------------------------------


class _PromptResult:
    def __init__(self, value):
        self._value = value

    def execute(self):
        if isinstance(self._value, BaseException):
            raise self._value
        return self._value


class _FakePromptBackend:
    def __init__(self, values):
        self._values = iter(values)
        self.calls = []

    def _record(self, prompt_type, **kwargs):
        self.calls.append((prompt_type, kwargs))
        return _PromptResult(next(self._values))

    def select(self, **kwargs):
        return self._record("select", **kwargs)

    def confirm(self, **kwargs):
        return self._record("confirm", **kwargs)

    def text(self, **kwargs):
        return self._record("text", **kwargs)


def _save_global_settings(home: Path, **overrides):
    from brainpack.settings import BrainpackSettings, save_settings

    save_settings(
        BrainpackSettings(
            version=1,
            setup_completed=True,
            preferred_transcription_backend=overrides.get(
                "preferred_transcription_backend",
                "faster-whisper",
            ),
            preferred_whisper_model=overrides.get("preferred_whisper_model", "small"),
            preferred_llm_model=overrides.get("preferred_llm_model", "llama3.2"),
        )
    )


def _make_config(
    sources,
    embedding_model="all-MiniLM-L6-v2",
    episode_limit=20,
    llm="ollama",
):
    """Helper to build a mock PackConfig with SourceEntry objects."""
    cfg = MagicMock()
    cfg.sources = sources
    cfg.embedding_model = embedding_model
    cfg.name = "test-pack"
    cfg.episode_limit = episode_limit
    cfg.llm = llm
    return cfg


def _mark_pack_ready(pack_dir: Path, *, last_build_at: str = "2026-03-13T10:00:00+00:00"):
    """Persist the minimal ready state needed for query command tests."""
    from brainpack.inventory import pack_config_hash
    from brainpack.pack_state import save_state

    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {},
            "audio_steps": {},
            "last_build_at": last_build_at,
            "last_built_pack_hash": pack_config_hash(pack_dir),
        },
    )


def _mark_pack_needs_build(
    pack_dir: Path,
    *,
    last_build_at: str = "2026-03-13T10:00:00+00:00",
):
    """Persist a stale build state so lifecycle tests hit needs-build paths."""
    from brainpack.pack_state import save_state

    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {},
            "audio_steps": {},
            "last_build_at": last_build_at,
            "last_built_pack_hash": "outdated-hash",
        },
    )


def _mark_pack_failed(pack_dir: Path):
    """Persist a failed build state so lifecycle tests hit error paths."""
    from brainpack.pack_state import save_state

    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {
                "https://example.com/article": {"status": "failed"},
            },
            "audio_steps": {},
        },
    )


def _mark_pack_mixed_result(
    pack_dir: Path,
    *,
    last_build_at: str = "2026-03-21T10:00:00+00:00",
):
    """Persist a mixed-result build state with indexed content plus one failed source."""
    from brainpack.inventory import pack_config_hash
    from brainpack.pack_state import save_state

    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {
                "url:done": {
                    "status": "done",
                    "url": "https://example.com/article",
                    "title": "Ready source",
                },
                "url:failed": {
                    "status": "failed",
                    "url": "https://example.com/missed",
                    "reason": "download failed after retry",
                },
            },
            "audio_steps": {},
            "last_build_at": last_build_at,
            "last_built_pack_hash": pack_config_hash(pack_dir),
        },
    )


def _mark_pack_partially_ready(
    pack_dir: Path,
    *,
    ready_url: str = "https://example.com/article-1",
    last_build_at: str = "2026-03-21T10:00:00+00:00",
):
    """Persist a partial-progress build state with some ready sources and some pending."""
    from brainpack.pack_state import save_state

    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {
                ready_url: {
                    "status": "done",
                    "url": ready_url,
                    "title": "Ready source",
                },
            },
            "audio_steps": {},
            "last_build_at": last_build_at,
            "last_built_pack_hash": "outdated-hash",
            "last_build_result": "partial-selection",
        },
    )


def _mark_pack_incrementally_ready(
    pack_dir: Path,
    *,
    urls: list[str] | None = None,
):
    """Persist an all-sources-indexed state produced via repeated --source builds."""
    from brainpack.pack_state import save_state

    ready_urls = urls or [
        "https://example.com/article-1",
        "https://example.com/article-2",
    ]
    processed = {
        url: {
            "status": "done",
            "url": url,
            "title": f"Ready source {index}",
        }
        for index, url in enumerate(ready_urls, start=1)
    }
    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": processed,
            "audio_steps": {},
            "last_build_result": "partial-selection",
        },
    )


@pytest.fixture
def tmp_pack_root(tmp_path):
    """Create a ~/.brainpacks-like structure with a 'test-pack' subdirectory."""
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\n"
        "description: Test pack\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    return packs_root, pack_dir


@pytest.fixture
def tmp_pack_dir(tmp_path):
    """A temporary pack directory with a minimal pack.yaml."""
    pack_dir = tmp_path / "test-pack"
    pack_dir.mkdir()
    pack_yaml = pack_dir / "pack.yaml"
    pack_yaml.write_text(
        "name: test-pack\n"
        "description: Test pack\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    return pack_dir


@pytest.fixture
def pack_state_with_model(tmp_pack_dir):
    """A pack directory with meta.json containing embedding_model set."""
    state = {
        "embedding_model": "all-MiniLM-L6-v2",
        "processed": {},
    }
    (tmp_pack_dir / "meta.json").write_text(json.dumps(state))
    return tmp_pack_dir


@pytest.fixture
def mock_model():
    """A mock SentenceTransformer that returns deterministic float embeddings."""
    import numpy as np
    model = MagicMock()
    model.encode.return_value = np.array([[0.1] * 384])
    return model


@pytest.fixture
def mock_openai_client():
    """A mock OpenAI client that returns a canned LLM response."""
    client = MagicMock()
    choice = MagicMock()
    choice.message.content = "Test answer. Sources: [1] Example Article"
    client.chat.completions.create.return_value = MagicMock(choices=[choice])
    return client
