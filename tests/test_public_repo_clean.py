import re
from pathlib import Path


def test_public_repo_clean():
    repo = Path(__file__).resolve().parents[1]
    assert not (repo / "review_only").exists()
    text_parts = []
    for p in repo.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".md", ".py", ".json", ".csv", ".ipynb", ".txt", ".gitignore"}:
            text_parts.append(p.read_text(encoding="utf-8", errors="ignore"))
    text = "\n".join(text_parts)
    forbidden_literals = ["Admin" + "istrator", "C:" + "\\" + "Users", "提交" + "答卷" + "时间", "来源" + "详情", "来自" + "IP", "学" + "号"]
    assert not any(x in text for x in forbidden_literals)
    assert not re.search(r"(?i)(api[_-]?key|password|secret|token)\s*[:=]", text)
