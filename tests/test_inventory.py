"""Focused inventory tests for Phase 12 lifecycle recap behavior."""
import json


def _write_pack(pack_dir, *, name="test-pack", llm="openai"):
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "pack.yaml").write_text(
        f"name: {name}\n"
        "description: Test pack\n"
        f"llm: {llm}\n"
        "sources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )


def test_inspect_pack_exposes_last_build_recap_for_human_consumers(tmp_path):
    """inspect_pack includes persisted last-build recap details for human renderers."""
    from brainpack.inventory import inspect_pack, save_pack_origin
    from brainpack.pack_state import save_state

    pack_dir = tmp_path / "test-pack"
    _write_pack(pack_dir)
    save_pack_origin(
        pack_dir,
        {
            "type": "file",
            "source": "/tmp/test-pack.yaml",
            "added_at": "2026-03-15T09:00:00+00:00",
            "last_updated_at": "2026-03-16T09:00:00+00:00",
            "last_update_summary": ["added one source"],
        },
    )
    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {},
            "audio_steps": {},
            "last_build_at": "2026-03-17T10:00:00+00:00",
            "last_built_pack_hash": "abc123",
            "last_build_result": "blocked",
            "last_build_summary": "Blocked after 1 source: ffmpeg missing",
        },
    )

    summary = inspect_pack(pack_dir, lambda _cfg: {"blockers": [], "warnings": []})

    assert summary["last_build_result"] == "blocked"
    assert summary["last_build_summary"] == "Blocked after 1 source: ffmpeg missing"
    assert summary["last_update_at"] == "2026-03-16T09:00:00+00:00"
    assert summary["last_update_summary"] == ["added one source"]


def test_machine_inventory_payloads_do_not_expand_with_build_recap_fields(tmp_path):
    """serialize_pack_summary/detail keep the current public machine shape."""
    from brainpack.inventory import (
        inspect_pack,
        serialize_pack_detail,
        serialize_pack_summary,
    )
    from brainpack.pack_state import save_state

    pack_dir = tmp_path / "test-pack"
    _write_pack(pack_dir)
    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {},
            "audio_steps": {},
            "last_build_at": "2026-03-17T10:00:00+00:00",
            "last_built_pack_hash": "abc123",
            "last_build_result": "mixed",
            "last_build_summary": "Completed with issues: 2 indexed, 1 failed",
        },
    )

    summary = inspect_pack(pack_dir, lambda _cfg: {"blockers": [], "warnings": []})
    public_summary = serialize_pack_summary(summary)
    public_detail = serialize_pack_detail(summary)

    assert "last_build_result" not in public_summary
    assert "last_build_summary" not in public_summary
    assert "last_build_result" not in public_detail
    assert "last_build_summary" not in public_detail
    assert set(public_summary.keys()) == {
        "name",
        "status",
        "type",
        "provider",
        "source_count",
        "recent_summary",
        "next_action",
        "blockers",
        "warnings",
        "origin",
    }
    assert set(public_detail.keys()) == {
        "name",
        "status",
        "type",
        "provider",
        "source_count",
        "recent_summary",
        "next_action",
        "blockers",
        "warnings",
        "origin",
        "last_build_at",
        "last_update_at",
        "last_update_summary",
    }


def test_inspect_pack_recap_is_visible_after_blocked_build(tmp_path):
    """inspect_pack surfaces last_build_result='blocked' written by a blocked build run."""
    from brainpack.inventory import inspect_pack
    from brainpack.pack_state import save_state

    pack_dir = tmp_path / "test-pack"
    _write_pack(pack_dir)
    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {},
            "audio_steps": {},
            "last_build_at": "2026-03-17T10:00:00+00:00",
            "last_built_pack_hash": "abc123",
            "last_build_result": "blocked",
            "last_build_summary": "Blocked: 1 source, ffmpeg missing",
        },
    )

    summary = inspect_pack(pack_dir, lambda _cfg: {"blockers": [], "warnings": []})

    assert summary["last_build_result"] == "blocked"
    assert "ffmpeg" in (summary["last_build_summary"] or "")


def test_inspect_pack_recap_is_none_when_build_not_run(tmp_path):
    """inspect_pack returns None for last_build_result when the pack has never been built."""
    from brainpack.inventory import inspect_pack

    pack_dir = tmp_path / "test-pack"
    _write_pack(pack_dir)
    # No save_state call — fresh pack

    summary = inspect_pack(pack_dir, lambda _cfg: {"blockers": [], "warnings": []})

    assert summary["last_build_result"] is None
    assert summary["last_build_summary"] is None
