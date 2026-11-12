"""Analysis: taxonomy, metrics, and reports."""

from __future__ import annotations

from paybench.analysis.metrics import bootstrap_ci, summarize
from paybench.analysis.report import render_markdown
from paybench.analysis.taxonomy import classify

__all__ = ["bootstrap_ci", "classify", "render_markdown", "summarize"]
