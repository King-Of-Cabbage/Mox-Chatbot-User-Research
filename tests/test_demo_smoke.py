import json
import os
import subprocess
import sys
from pathlib import Path


def test_demo_smoke(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    out = tmp_path / "demo_results"
    cmd = [sys.executable, str(repo / "src" / "run_analysis.py"), "--mode", "demo", "--input", str(repo / "data" / "synthetic_example.csv"), "--output", str(out)]
    completed = subprocess.run(cmd, cwd=repo, text=True, capture_output=True, check=True)
    assert (out / "demo_metrics.json").exists()
    assert (out / "tables" / "model_coefficients.csv").exists()
    assert list((out / "figures").glob("*.png"))
    text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in out.rglob("*") if p.is_file() and p.suffix.lower() in {".json", ".csv", ".py", ".md", ".txt"})
    forbidden = ["姓名", "来自" + "IP", "提交" + "答卷" + "时间", "来源" + "详情", "C:" + "\\" + "Users", "Admin" + "istrator", "Desk" + "top"]
    assert not any(token in text for token in forbidden)
    assert "error" not in completed.stderr.lower()
