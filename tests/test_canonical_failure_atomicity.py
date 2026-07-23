import pandas as pd
import pytest

from src.run_analysis import FIELD_REGISTRY, _atomic_output, run_analysis


def test_canonical_failure_does_not_overwrite_existing_output(tmp_path):
    columns = [spec["exact"][0] for spec in FIELD_REGISTRY.values()]
    bad = pd.DataFrame([{c: 1 for c in columns}])
    bad[FIELD_REGISTRY["duration"]["exact"][0]] = "bad duration"
    xlsx = tmp_path / "bad.xlsx"
    bad.to_excel(xlsx, sheet_name="Sheet1", index=False)
    out = tmp_path / "out"
    out.mkdir()
    sentinel = out / "canonical_metrics.json"
    sentinel.write_text("sentinel", encoding="utf-8")
    try:
        run_analysis("canonical", xlsx, out)
    except Exception:
        pass
    assert sentinel.read_text(encoding="utf-8") == "sentinel"
    assert not (out / "tables").exists()


def test_atomic_output_restores_existing_directory_if_replacement_fails(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    sentinel = out / "keep.txt"
    sentinel.write_text("sentinel", encoding="utf-8")

    original_replace = type(out).replace
    calls = {"count": 0}

    def flaky_replace(self, target):
        calls["count"] += 1
        result = original_replace(self, target)
        if calls["count"] == 2:
            raise OSError("simulated replacement failure")
        return result

    monkeypatch.setattr(type(out), "replace", flaky_replace)

    with pytest.raises(OSError):
        _atomic_output(out, lambda tmp: (tmp / "new.txt").write_text("new", encoding="utf-8"))

    assert sentinel.read_text(encoding="utf-8") == "sentinel"
