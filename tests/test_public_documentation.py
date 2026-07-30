import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_markdown_excludes_private_identifiers_and_paths():
    banned = [
        "".join(["SHI", " ", "Wei", "kang"]),
        "".join(["C:", "\\", "Users"]),
        "".join(["Admin", "istrator"]),
        "review_only",
    ]
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for folder in [ROOT, ROOT / "docs"]
        for path in folder.glob("*.md")
    )
    for phrase in banned:
        assert phrase not in text


def test_private_or_respondent_level_files_are_not_present():
    forbidden_suffixes = {".xlsx", ".xls", ".docx", ".pdf", ".zip", ".rar", ".7z"}
    skip_dirs = {".git", ".venv", ".venv-ci", ".venv-ci311", ".venv-ci312", "local_results", ".pytest_cache", "__pycache__"}
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT).as_posix()
        if any(part in skip_dirs for part in path.relative_to(ROOT).parts):
            continue
        assert "review_only" not in rel
        if path.is_file():
            assert path.suffix.lower() not in forbidden_suffixes
            assert "respondent" not in path.name.lower()


def test_readme_uses_safe_canonical_command_placeholder():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "path/to/private_questionnaire.xlsx" in readme
    assert "<private_questionnaire.xlsx>" not in readme
    assert "--input  --output" not in readme
    assert ".\\.venv\\Scripts\\Activate.ps1" in readme
    assert ".venv\\Scripts\\activate.bat" in readme
    assert ".venv\\S cripts\\a ctivate" not in readme
    assert "python src/run_analysis.py --mode demo --input data/synthetic_example.csv --output local_results/demo" in readme
    assert (
        "python src/run_analysis.py --mode canonical --input path/to/private_questionnaire.xlsx --output local_results/canonical"
        in readme
    )


def test_public_text_separates_synthetic_demo_from_empirical_results():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    data_readme = (ROOT / "data" / "README.md").read_text(encoding="utf-8")
    assert "does not reproduce the empirical coefficients" in readme
    assert "respondent-level source data cannot be published" in readme
    assert "is not a sample from the real questionnaire" in data_readme


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
