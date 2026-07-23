import json
import math
from pathlib import Path

from src.run_analysis import RANDOM_SEED, run_analysis


def test_demo_smoke(tmp_path):
    root = Path(__file__).resolve().parents[1]
    out = tmp_path / "demo"
    run_analysis("demo", root / "data" / "synthetic_example.csv", out)
    metrics = json.loads((out / "demo_metrics.json").read_text(encoding="utf-8"))
    assert metrics["run_metadata"]["random_seed"] == RANDOM_SEED
    assert set(metrics["models"]) == {"Model A", "Model B", "Model C", "Moderation"}
    assert {name: model["n"] for name, model in metrics["models"].items()} == {
        "Model A": 32,
        "Model B": 32,
        "Model C": 32,
        "Moderation": 32,
    }
    assert "bank_security_control" in metrics["models"]["Model A"]["params"]
    snapshots = {
        ("Model A", "bank_security_control"): 0.18988535063546952,
        ("Model B", "bank_satisfaction"): 0.1254698341468792,
        ("Model C", "bank_service"): 0.15391806249384216,
        ("Moderation", "interaction"): -0.5984828627132822,
    }
    for (model_name, term), expected in snapshots.items():
        observed = metrics["models"][model_name]["params"][term]["coef"]
        assert math.isclose(observed, expected, rel_tol=1e-10, abs_tol=1e-10)
    assert ("bank_" + "trustsec") not in json.dumps(metrics)
    assert len(list((out / "figures").glob("*.png"))) >= 5
    assert (out / "tables" / "model_coefficients.csv").exists()
