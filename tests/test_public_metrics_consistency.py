import csv
import json
from pathlib import Path


def test_public_metrics_tables_and_readme_are_consistent():
    root = Path(__file__).resolve().parents[1]
    metrics = json.loads((root / "results" / "canonical_metrics.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((root / "results" / "tables" / "model_coefficients.csv").open(encoding="utf-8-sig")))
    terms = {(r["model"], r["term"]): r for r in rows}
    assert ("Model A", "bank_security_control") in terms
    assert all(("bank_" + "trustsec") not in key[1] for key in terms)
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert f"{metrics['models']['Model B']['r_squared']:.3f}" in readme
    assert "bank_security_control" in readme
    assert ("bank_" + "trustsec") not in readme
