"""Normalized build-report seam for progress tracking and final summaries.

BuildReport accumulates per-source outcomes during a build run and generates:
- A compact summary table for human output
- A single verdict line (success / completed with issues / blocked)
- A short persistable summary string for later status inspection

All rendering logic stays here so cli.py only appends events and calls render.
JSON/MCP contracts are unaffected — this module is human-output-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BuildEvent:
    """One source outcome recorded during the build loop."""

    title: str
    status: str  # "done" | "skipped" | "failed" | "blocked"
    new: int = 0
    skipped: int = 0
    failure_reason: str = ""


@dataclass
class BuildReport:
    """Accumulate source outcomes and render the final build output."""

    events: List[BuildEvent] = field(default_factory=list)

    # ------------------------------------------------------------------ append

    def record(
        self,
        title: str,
        status: str,
        *,
        new: int = 0,
        skipped: int = 0,
        failure_reason: str = "",
    ) -> None:
        """Append one source result to the report."""
        self.events.append(
            BuildEvent(
                title=title,
                status=status,
                new=new,
                skipped=skipped,
                failure_reason=failure_reason,
            )
        )

    # ------------------------------------------------------------------ totals

    @property
    def total_new(self) -> int:
        return sum(e.new for e in self.events)

    @property
    def total_skipped(self) -> int:
        return sum(e.skipped for e in self.events)

    @property
    def failed_events(self) -> List[BuildEvent]:
        return [e for e in self.events if e.status == "failed"]

    @property
    def blocked_events(self) -> List[BuildEvent]:
        return [e for e in self.events if e.status == "blocked"]

    @property
    def had_issues(self) -> bool:
        return bool(self.failed_events or self.blocked_events)

    # ------------------------------------------------------------------ result

    @property
    def result(self) -> str:
        """Return a short result token for state persistence.

        Possible values: "success" | "mixed" | "blocked"
        """
        if not self.events:
            return "success"
        if self.blocked_events and not self.failed_events and self.total_new == 0:
            return "blocked"
        if self.had_issues:
            return "mixed"
        return "success"

    @property
    def summary_line(self) -> str:
        """Return a one-line build summary suitable for state persistence."""
        n = self.total_new
        failed = len(self.failed_events)
        blocked = len(self.blocked_events)
        if self.result == "success":
            if n == 0:
                return "Build complete — all sources up to date."
            return f"Build complete — {n} new chunk(s) indexed."
        if self.result == "blocked":
            return (
                f"Build completed with issues: "
                f"{blocked} source(s) blocked, {n} new chunk(s) indexed."
            )
        parts = []
        if n > 0:
            parts.append(f"{n} indexed")
        if failed:
            parts.append(f"{failed} failed")
        if blocked:
            parts.append(f"{blocked} blocked")
        return "Build completed with issues: " + ", ".join(parts) + "."

    # ------------------------------------------------------------------ render

    def render_table(self) -> str:
        """Return the compact summary table as a string."""
        header = f"{'Source':<40} {'Status':<10} {'New(chunks)':>11} {'Skipped(chunks)':>15}"
        sep = f"{'-'*40} {'-'*10} {'-'*11} {'-'*15}"
        rows = []
        for e in self.events:
            title_col = e.title[:40]
            new_col = "-" if e.status == "skipped" else str(e.new)
            skipped_col = "-" if e.status == "skipped" else str(e.skipped)
            rows.append(f"{title_col:<40} {e.status:<10} {new_col:>11} {skipped_col:>15}")
        return "\n".join([header, sep] + rows)

    def render_verdict(self) -> str:
        """Return the single verdict line to print after the table."""
        n = self.total_new
        if self.result == "success":
            if n == 0:
                return f"Build complete — 0 new chunks, all sources up to date."
            return f"Build complete — {n} new chunk(s) indexed."
        if self.result == "blocked":
            return (
                f"Build completed with issues — "
                f"{len(self.blocked_events)} source(s) blocked. "
                f"{n} new chunk(s) indexed."
            )
        # mixed
        failed = len(self.failed_events)
        blocked = len(self.blocked_events)
        issue_parts = []
        if failed:
            issue_parts.append(f"{failed} failed")
        if blocked:
            issue_parts.append(f"{blocked} blocked")
        return (
            f"Build completed with issues — "
            + ", ".join(issue_parts)
            + f". {n} new chunk(s) indexed."
        )

    def render_issues_recap(self) -> Optional[str]:
        """Return a short recap of failed/blocked sources, or None if no issues."""
        problem_events = self.failed_events + self.blocked_events
        if not problem_events:
            return None
        lines = ["Issues:"]
        for e in problem_events:
            suffix = f" ({e.failure_reason})" if e.failure_reason else ""
            lines.append(f"  [{e.status}] {e.title[:60]}{suffix}")
        return "\n".join(lines)
