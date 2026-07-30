from pathlib import Path

from scripts.validate_data_boundaries import validate


def test_public_files_have_no_sensitive_data_boundary_findings():
    root = Path(__file__).resolve().parents[1]
    findings = validate(root)
    runtime_types = {"runtime cache", "temporary artifact"}
    assert [f for f in findings if f["type"] not in runtime_types] == []
