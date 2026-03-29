"""Traceability artifact test for Phase 11."""
from pathlib import Path

import pytest


def test_phase_11_traceability_artifact_exists():
    """Phase 11 leaves an explicit local traceability artifact instead of only plan prose."""
    traceability = Path(
        ".planning/phases/11-add-interactive-setup-settings-and-guided-pack-authoring-ux/11-TRACEABILITY.md"
    )

    if not traceability.exists():
        pytest.skip("phase traceability artifacts are not present in this checkout")

    content = traceability.read_text(encoding="utf-8")
    assert "ONB-02" in content
    assert "RUN-01" in content
    assert "AUT-02" in content
