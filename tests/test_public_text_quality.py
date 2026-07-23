import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_markdown_avoids_internal_or_machine_like_phrasing():
    banned = [
        "".join(["Chat", "GPT"]),
        "".join(["Co", "dex"]),
        "".join(["generated", " by ", "AI"]),
        "".join(["AI", "-generated"]),
        "".join(["as ", "an ", "AI"]),
        "".join(["release", "-ready ", "candidate"]),
        "".join(["Why Legacy", " Results Were ", "Replaced"]),
        "".join(["The wording here", " avoids ", "implying"]),
        "".join(["SHI", " ", "Wei", "kang"]),
        "".join(["PUBLICATION", " STATUS:", " NOT YET", " APPROVED"]),
    ]
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for folder in [ROOT, ROOT / "docs"]
        for path in folder.glob("*.md")
    )
    for phrase in banned:
        assert phrase not in text


def test_readme_uses_safe_canonical_command_placeholder():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "path/to/private_questionnaire.xlsx" in readme
    assert "<private_questionnaire.xlsx>" not in readme
    assert "--input  --output" not in readme


def test_notebook_is_public_safe_and_demo_first():
    nb = json.loads((ROOT / "notebooks" / "01_analysis.ipynb").read_text(encoding="utf-8"))
    source = "\n".join("".join(cell.get("source", [])) for cell in nb["cells"])
    assert "RUN_CANONICAL = False" in source
    assert "PRIVATE_QUESTIONNAIRE = None" in source
    assert 'Path("")' not in source
    assert 'Path(\'\')' not in source
    assert 'repo_root / "local_results" / "demo"' in source
    assert 'repo_root / "local_results" / "canonical"' in source
    for cell in nb["cells"]:
        if cell.get("cell_type") == "code":
            assert cell.get("execution_count") is None
            assert cell.get("outputs") == []
