"""Tests for CLI help, about, and top-level framing — covers CLI-01."""
import pytest
from typer.testing import CliRunner


def test_help_frames_agent_and_local_modes():
    """beyin --help should frame the product around agent and local-model use."""
    from beyin.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "agent" in result.output.lower()
    assert "local model" in result.output.lower()
    assert "build" in result.output
    assert "query" in result.output


def test_help_command_alias_shows_top_level_framing():
    """beyin help should preserve the same top-level onboarding framing."""
    from beyin.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["help"])

    assert result.exit_code == 0
    assert "Beyin v0.1.0" in result.output
    assert "append --help to any command" in result.output
    assert "agent" in result.output.lower()
    assert "Pack lifecycle:" in result.output
    assert "Inspect and retrieve:" in result.output
    assert "Key flags" not in result.output
    assert "https://github.com/buralog/beyin" in result.output


def test_about_command_shows_short_project_summary_and_repo_url():
    """beyin about should explain the project briefly and point to the repo."""
    from beyin.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["about"])

    assert result.exit_code == 0
    assert "local knowledge" in result.output.lower() or "local knowledge packs" in result.output.lower()
    assert "mcp" in result.output.lower()
    assert "https://github.com/buralog/beyin" in result.output


def test_local_mode_command_help_and_agent_server_help_use_new_positioning():
    """Command help should position query as local mode and mcp-server for agents."""
    from beyin.cli import app

    runner = CliRunner()

    query_help = runner.invoke(app, ["query", "--help"])
    mcp_help = runner.invoke(app, ["mcp-server", "--help"])

    assert query_help.exit_code == 0
    assert "local mode" in query_help.output.lower()
    assert mcp_help.exit_code == 0
    assert "agent" in mcp_help.output.lower()
    assert "stdio" in mcp_help.output.lower()


@pytest.mark.parametrize(
    ("argv", "missing_label", "help_needle", "extra_needle"),
    [
        (
            ["status"],
            "<pack>",
            "Inspect one installed pack in detail.",
            "--json",
        ),
        (
            ["query"],
            "<pack>",
            "Query a pack directly in local model mode and receive a cited LLM answer.",
            "--json",
        ),
        (
            ["build"],
            "<pack>",
            "Build or incrementally update a pack from its pack.yaml sources.",
            "--model",
        ),
        (
            ["add"],
            "<source>",
            "Add a shared pack from a local path, URL, or marketplace-style id.",
            "Arguments",
        ),
        (
            ["add-source"],
            "<pack>",
            "Add one or more sources to an existing pack's pack.yaml.",
            "--build",
        ),
        (
            ["remove-source"],
            "<pack>",
            "Remove one or more sources from an existing pack by index or text match.",
            "--build",
        ),
        (
            ["remove"],
            "<pack>",
            "Permanently remove one installed pack and all its data.",
            "--yes",
        ),
        (
            ["update"],
            "<pack>",
            "Fetch new sources and rebuild a pack incrementally.",
            "--model",
        ),
    ],
)
def test_missing_required_arguments_show_help_without_help_option(argv, missing_label, help_needle, extra_needle):
    """Missing required args should show help with args first, then visible options, and no --help row."""
    from beyin.cli import app

    runner = CliRunner()
    result = runner.invoke(app, argv)

    assert result.exit_code == 2
    assert "Beyin v0.1.0" in result.output
    assert f"Missing required argument: {missing_label}" in result.output
    assert "Usage:" in result.output
    assert help_needle in result.output
    assert extra_needle in result.output
    assert "[OPTIONS]" not in result.output
    assert "--help" not in result.output
    assert "Show this message and exit." not in result.output
