"""Machine-safe CLI contract tests."""

import json

from brainpack.machine_output import (
    CLI_SCHEMA_VERSION,
    MachineExit,
    build_error_envelope,
    build_success_envelope,
    emit_json,
    run_machine_command,
)


def test_success_envelope_uses_shared_schema_and_top_level_shape():
    """Success responses keep one stable top-level envelope."""
    envelope = build_success_envelope(
        command="list",
        data={"packs": []},
    )

    assert envelope == {
        "ok": True,
        "meta": {
            "schema": CLI_SCHEMA_VERSION,
            "command": "list",
        },
        "data": {"packs": []},
        "warnings": [],
    }


def test_error_envelope_uses_shared_schema_and_top_level_shape():
    """Failure responses reuse the same envelope contract."""
    envelope = build_error_envelope(
        command="status",
        error_code="pack_not_found",
        message="Pack 'missing-pack' is not installed.",
        pack="missing-pack",
        details={"next_action": "brainpack create"},
    )

    assert envelope == {
        "ok": False,
        "meta": {
            "schema": CLI_SCHEMA_VERSION,
            "command": "status",
            "pack": "missing-pack",
        },
        "error": {
            "code": "pack_not_found",
            "message": "Pack 'missing-pack' is not installed.",
            "details": {"next_action": "brainpack create"},
        },
        "warnings": [],
    }


def test_emit_json_writes_one_schema_document_to_stdout(capsys):
    """Machine JSON emission writes one parseable document and nothing else."""
    emit_json(
        build_success_envelope(
            command="list",
            data={"packs": []},
        )
    )

    captured = capsys.readouterr()

    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["meta"]["schema"] == CLI_SCHEMA_VERSION
    assert payload["ok"] is True
    assert captured.out.strip().startswith("{")
    assert captured.out.strip().endswith("}")


def test_machine_exit_code_taxonomy_is_small_and_stable():
    """Covered machine failures map onto the fixed exit-code taxonomy."""
    usage_error = MachineExit.usage(
        "interactive_json_not_supported",
        "brainpack chat --json requires a question argument",
    )
    precondition_error = MachineExit.precondition(
        "pack_not_found",
        "Pack 'missing-pack' is not installed.",
    )

    assert usage_error.exit_code == 2
    assert precondition_error.exit_code == 3


def test_run_machine_command_normalizes_unexpected_error_to_shared_envelope_and_exit_code(
    capsys,
):
    """Unexpected exceptions become one shared machine error response."""

    def explode() -> dict:
        raise RuntimeError("boom")

    exit_code = run_machine_command(
        command="query",
        pack="demo-pack",
        action=explode,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 4
    assert captured.err == ""
    assert payload == {
        "ok": False,
        "meta": {
            "schema": CLI_SCHEMA_VERSION,
            "command": "query",
            "pack": "demo-pack",
        },
        "error": {
            "code": "unexpected_error",
            "message": "Unexpected error while running command.",
            "details": {"type": "RuntimeError"},
        },
        "warnings": [],
    }
