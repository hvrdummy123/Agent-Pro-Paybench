"""Interactive site pages: playground + compare."""

from __future__ import annotations

from pathlib import Path

from paybench.site.build import build_site
from paybench.site.traces import collect_compare_payload


def test_compare_payload_oracle_pass_naive_fail() -> None:
    payload = collect_compare_payload()
    assert payload["task_id"] == "transfer_timeout_after_commit"
    assert payload["oracle"]["success"] is True
    assert payload["naive"]["success"] is False
    assert any(e.get("fault") == "TIMEOUT_AFTER_COMMIT" for e in payload["oracle"]["case_log"])
    assert any(e.get("fault") == "TIMEOUT_AFTER_COMMIT" for e in payload["naive"]["case_log"])


def test_site_writes_playground_and_compare(tmp_path: Path) -> None:
    # Minimal empty run dir with empty episodes is ok; pages still generate
    run = tmp_path / "run"
    run.mkdir()
    (run / "episodes.jsonl").write_text("", encoding="utf-8")
    out = tmp_path / "site"
    build_site([run], out, repo_root=Path.cwd())
    play = (out / "playground.html").read_text(encoding="utf-8")
    cmp = (out / "compare.html").read_text(encoding="utf-8")
    assert "playground.js" in play
    assert "TIMEOUT" in play or "timeout" in play.lower()
    assert "compare.js" in cmp
    assert "PAYBENCH_COMPARE" in cmp
    assert (out / "static" / "playground.js").is_file()
    assert (out / "static" / "compare.js").is_file()
    assert 'href="playground.html"' in (out / "index.html").read_text(encoding="utf-8")
