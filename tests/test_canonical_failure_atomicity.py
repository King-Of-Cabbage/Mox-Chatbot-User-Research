import pandas as pd

from src.run_analysis import FIELD_REGISTRY, run_analysis


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
