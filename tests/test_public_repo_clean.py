from pathlib import Path

from scripts.validate_release_tree import validate


def test_public_repo_has_no_sensitive_release_findings():
    root = Path(__file__).resolve().parents[1]
    findings = validate(root)
    runtime_types = {"runtime cache", "temporary artifact"}
    assert [f for f in findings if f["type"] not in runtime_types] == []


def test_review_only_not_present():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "review_only").exists()
