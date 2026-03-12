"""Tests for pack_state.py — covers ING-05, PIP-06, SAF-01."""
import pytest


def test_load_state_empty(tmp_pack_dir):
    """load_state returns default state when no meta.json exists."""
    from brainpack.pack_state import load_state
    state = load_state(tmp_pack_dir)
    assert state["embedding_model"] is None
    assert state["processed"] == {}


def test_save_and_load_state_roundtrip(tmp_pack_dir):
    """save_state + load_state round-trips state through disk as human-readable JSON."""
    import json
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
    """mark_processed sets state['processed'][url] = {'title': ..., 'status': 'done'}."""
    from brainpack.pack_state import load_state, mark_processed
    state = load_state(tmp_pack_dir)
    url = "https://example.com/article"
    mark_processed(state, url, "Example Article")
    entry = state["processed"][url]
    assert entry["title"] == "Example Article"
    assert entry["status"] == "done"
