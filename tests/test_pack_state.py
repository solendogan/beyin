"""Tests for pack_state.py — covers ING-05, PIP-06, SAF-01, ING-04, PCK-06."""
import json

import pytest


def test_load_state_empty(tmp_pack_dir):
    """load_state returns default state when no meta.json exists."""
    from brainpack.pack_state import load_state
    state = load_state(tmp_pack_dir)
    assert state["embedding_model"] is None
    assert state["processed"] == {}


def test_save_and_load_state_roundtrip(tmp_pack_dir):
    """save_state + load_state round-trips state through disk as human-readable JSON."""
    from brainpack.pack_state import load_state, save_state
    state = load_state(tmp_pack_dir)
    state["embedding_model"] = "all-MiniLM-L6-v2"
    save_state(tmp_pack_dir, state)

    meta_path = tmp_pack_dir / "meta.json"
    assert meta_path.exists()
    raw = meta_path.read_text()
    # Human-readable: must be indented (indent=2)
    parsed = json.loads(raw)
    assert "  " in raw  # indent=2 means spaces present

    reloaded = load_state(tmp_pack_dir)
    assert reloaded["embedding_model"] == "all-MiniLM-L6-v2"


class TestCanonicalSourceIds:
    """Canonical source identity behavior for Phase 4."""

    def test_youtube_source_id_prefers_provider_specific_identity(self):
        """YouTube URLs use the stable video ID instead of a URL hash."""
        from brainpack.source_ids import canonical_source_id

        assert (
            canonical_source_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            == "youtube:dQw4w9WgXcQ"
        )

    def test_podcast_source_id_uses_guid_when_available(self):
        """Podcast GUIDs override unstable CDN URLs when provided."""
        from brainpack.source_ids import canonical_source_id

        guid = "tag:example.com,2026:episode-42"
        first = canonical_source_id(
            "https://cdn.example.com/audio.mp3?token=abc",
            source_type="podcast",
            guid=guid,
        )
        second = canonical_source_id(
            "https://mirror.example.com/audio.mp3?token=xyz",
            source_type="podcast",
            guid=guid,
        )

        assert first == second
        assert first.startswith("podcast:")

    def test_url_fallback_ignores_fragment_only_changes(self):
        """URL fallback strips fragments before deriving the canonical ID."""
        from brainpack.source_ids import canonical_source_id

        first = canonical_source_id("https://example.com/posts/runtime-correctness#intro")
        second = canonical_source_id("https://example.com/posts/runtime-correctness#summary")

        assert first == second
        assert first.startswith("url:")


def test_model_mismatch_raises(pack_state_with_model):
    """check_model_provenance raises typer.BadParameter with both model names when models differ."""
    import typer
    from brainpack.pack_state import load_state, check_model_provenance
    state = load_state(pack_state_with_model)
    with pytest.raises(typer.BadParameter) as exc_info:
        check_model_provenance(state, "different-model", pack_name="test-pack")
    msg = str(exc_info.value)
    assert "all-MiniLM-L6-v2" in msg
    assert "different-model" in msg


def test_model_match_does_not_raise(pack_state_with_model):
    """check_model_provenance does NOT raise when models match."""
    from brainpack.pack_state import load_state, check_model_provenance
    state = load_state(pack_state_with_model)
    # Should not raise
    check_model_provenance(state, "all-MiniLM-L6-v2", pack_name="test-pack")


def test_fresh_state_sets_model(tmp_pack_dir):
    """check_model_provenance on fresh state (embedding_model=None) sets state['embedding_model']."""
    from brainpack.pack_state import load_state, check_model_provenance
    state = load_state(tmp_pack_dir)
    assert state["embedding_model"] is None
    check_model_provenance(state, "all-MiniLM-L6-v2", pack_name="test-pack")
    assert state["embedding_model"] == "all-MiniLM-L6-v2"


def test_is_processed_skips_known_url(pack_state_with_model):
    """is_processed returns False for unknown URL, True after mark_processed."""
    from brainpack.pack_state import load_state, is_processed, mark_processed
    state = load_state(pack_state_with_model)
    url = "https://example.com/article"
    assert not is_processed(state, url)
    mark_processed(state, url, "Example Article")
    assert is_processed(state, url)


def test_mark_processed_sets_correct_structure(tmp_pack_dir):
    """mark_processed stores done state under the canonical source_id key."""
    from brainpack.pack_state import load_state, mark_processed
    state = load_state(tmp_pack_dir)
    url = "https://www.youtube.com/watch?v=abc123xyz00"
    mark_processed(state, url, "Example Article")
    entry = state["processed"]["youtube:abc123xyz00"]
    assert entry["title"] == "Example Article"
    assert entry["status"] == "done"
    assert entry["source_id"] == "youtube:abc123xyz00"
    assert entry["url"] == url


def test_mark_processed_and_lookup_use_canonical_source_id(tmp_pack_dir):
    """Equivalent YouTube URLs resolve to the same canonical processed record."""
    from brainpack.pack_state import load_state, is_processed, mark_processed

    state = load_state(tmp_pack_dir)
    mark_processed(
        state,
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "Example Video",
    )

    assert is_processed(state, "https://youtu.be/dQw4w9WgXcQ") is True
    assert list(state["processed"]) == ["youtube:dQw4w9WgXcQ"]


def test_load_state_upgrades_legacy_url_keyed_records(tmp_pack_dir):
    """load_state upgrades legacy raw-URL keyed records into canonical source records."""
    from brainpack.pack_state import load_state
    from brainpack.source_ids import canonical_source_id

    article_url = "https://example.com/posts/runtime-correctness#intro"
    youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    article_id = canonical_source_id(article_url)

    (tmp_pack_dir / "meta.json").write_text(
        json.dumps(
            {
                "embedding_model": "all-MiniLM-L6-v2",
                "processed": {
                    article_url: {"title": "Runtime Correctness", "status": "done"},
                    youtube_url: {"title": "Example Video", "status": "done"},
                },
                "audio_steps": {
                    "https://youtu.be/dQw4w9WgXcQ": {
                        "title": "Example Video",
                        "downloaded": True,
                        "transcribed": True,
                    }
                },
            }
        )
    )

    state = load_state(tmp_pack_dir)

    assert set(state["processed"]) == {article_id, "youtube:dQw4w9WgXcQ"}
    assert state["processed"][article_id]["url"] == article_url
    assert state["processed"]["youtube:dQw4w9WgXcQ"]["source_id"] == "youtube:dQw4w9WgXcQ"
    assert state["audio_steps"]["youtube:dQw4w9WgXcQ"]["source_id"] == "youtube:dQw4w9WgXcQ"
    assert state["audio_steps"]["youtube:dQw4w9WgXcQ"]["stages"] == {
        "downloaded": True,
        "transcribed": True,
    }


class TestAudioSteps:
    """Tests for audio step tracking functions — covers ING-04."""

    def test_get_audio_step_returns_empty_dict_for_unknown_url(self, tmp_pack_dir):
        """get_audio_step returns {} for unknown URL (no KeyError)."""
        from brainpack.pack_state import load_state, get_audio_step
        state = load_state(tmp_pack_dir)
        result = get_audio_step(state, "https://example.com/ep1")
        assert result == {}

    def test_mark_audio_step_downloaded(self, tmp_pack_dir):
        """mark_audio_step stores stages under the canonical source_id key."""
        from brainpack.pack_state import load_state, mark_audio_step
        state = load_state(tmp_pack_dir)
        url = "https://www.youtube.com/watch?v=ep100000001"
        mark_audio_step(state, url, "downloaded", title="Ep 1")
        assert state["audio_steps"]["youtube:ep100000001"]["stages"]["downloaded"] is True

    def test_mark_audio_step_accumulates(self, tmp_pack_dir):
        """mark_audio_step for transcribed keeps downloaded still True."""
        from brainpack.pack_state import load_state, mark_audio_step
        state = load_state(tmp_pack_dir)
        url = "https://www.youtube.com/watch?v=ep200000002"
        mark_audio_step(state, url, "downloaded", title="Ep 2")
        mark_audio_step(state, url, "transcribed")
        assert state["audio_steps"]["youtube:ep200000002"]["stages"]["transcribed"] is True
        assert state["audio_steps"]["youtube:ep200000002"]["stages"]["downloaded"] is True

    def test_is_audio_step_done_true_after_marking(self, tmp_pack_dir):
        """is_audio_step_done returns True after step is marked."""
        from brainpack.pack_state import load_state, mark_audio_step, is_audio_step_done
        state = load_state(tmp_pack_dir)
        url = "https://www.youtube.com/watch?v=ep300000003"
        mark_audio_step(state, url, "downloaded", title="Ep 3")
        assert is_audio_step_done(state, "https://youtu.be/ep300000003", "downloaded") is True

    def test_is_audio_step_done_false_for_unmarked_step(self, tmp_pack_dir):
        """is_audio_step_done returns False when only downloaded is marked, not transcribed."""
        from brainpack.pack_state import load_state, mark_audio_step, is_audio_step_done
        state = load_state(tmp_pack_dir)
        url = "https://example.com/ep4"
        mark_audio_step(state, url, "downloaded", title="Ep 4")
        assert is_audio_step_done(state, url, "transcribed") is False

    def test_is_audio_step_done_false_for_unknown_url(self, tmp_pack_dir):
        """is_audio_step_done returns False for unknown URL (no KeyError)."""
        from brainpack.pack_state import load_state, is_audio_step_done
        state = load_state(tmp_pack_dir)
        assert is_audio_step_done(state, "https://example.com/unknown", "downloaded") is False

    def test_load_state_without_audio_steps_works_with_get_audio_step(self, tmp_pack_dir):
        """load_state on meta.json without 'audio_steps' key works with get_audio_step."""
        from brainpack.pack_state import load_state, get_audio_step
        # Write a meta.json that lacks audio_steps
        (tmp_pack_dir / "meta.json").write_text(json.dumps({
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {},
        }))
        state = load_state(tmp_pack_dir)
        assert state["audio_steps"] == {}
        # get_audio_step must not raise
        result = get_audio_step(state, "https://example.com/ep")
        assert result == {}
