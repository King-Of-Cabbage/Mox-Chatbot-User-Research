import json
from pathlib import Path

from src.run_analysis import RANDOM_SEED, run_analysis


def test_demo_smoke(tmp_path):
    root = Path(__file__).resolve().parents[1]
    out = tmp_path / "demo"
    run_analysis("demo", root / "data" / "synthetic_example.csv", out)
    metrics = json.loads((out / "demo_metrics.json").read_text(encoding="utf-8"))
    assert metrics["run_metadata"]["random_seed"] == RANDOM_SEED
    assert set(metrics["models"]) == {"Model A", "Model B", "Model C", "Moderation"}
    assert metrics["models"]["Model B"]["n"] > 20
    assert "bank_security_control" in metrics["models"]["Model A"]["params"]
    assert ("bank_" + "trustsec") not in json.dumps(metrics)
    assert len(list((out / "figures").glob("*.png"))) >= 5
    assert (out / "tables" / "model_coefficients.csv").exists()
