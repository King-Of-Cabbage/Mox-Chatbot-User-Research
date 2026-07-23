import argparse
import json
import re
from pathlib import Path

TEXT_EXTS = {".md", ".py", ".json", ".csv", ".ipynb", ".txt", ".gitignore", ".yml", ".yaml"}
CACHE_NAMES = {".pytest_cache", "__pycache__"}
TEMP_SUFFIXES = {".pyc", ".log", ".tmp"}
FORBIDDEN_SUFFIXES = {".xlsx", ".xls", ".docx", ".pdf", ".zip", ".rar", ".7z"}
SKIP_DIR_NAMES = {".git", ".venv", ".venv-ci", ".venv-ci311", ".venv-ci312", "local_results"}


def _join(*parts):
    return "".join(parts)


def checks():
    student_label = _join("\u5b66", "\u53f7")
    coauthor_full = _join("SHI", " ", "Wei", "kang")
    status_marker = _join("PUBLICATION", " STATUS:", " NOT YET", " APPROVED")
    respondent_ip = _join("\u6765\u81ea", "IP")
    submission_time = _join("\u63d0\u4ea4", "\u7b54\u5377", "\u65f6\u95f4")
    source_detail = _join("\u6765\u6e90", "\u8be6\u60c5")
    credential_words = _join("api", r"[_-]?", "key|pass", "word|sec", "ret|to", "ken")
    return [
        ("absolute user path", re.compile(r"C:" + re.escape("\\") + r"Users|Admin" + "istrator")),
        ("desktop path", re.compile(re.escape("\\") + r"Desk" + "top" + re.escape("\\"))),
        ("education identifier marker", re.compile(student_label + r"|" + "student" + r"\s*" + "id" + r"|" + "student" + "_" + "id", re.I)),
        ("coauthor full name", re.compile(coauthor_full, re.I)),
        ("release status marker", re.compile(status_marker)),
        ("survey ip metadata", re.compile(respondent_ip + r"|respondent\s*ip", re.I)),
        ("survey time metadata", re.compile(submission_time + r"|submission\s*timestamp", re.I)),
        ("survey source metadata", re.compile(source_detail + r"|source\s*detail", re.I)),
        ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
        ("credential", re.compile(r"(?i)(" + credential_words + r")\s*[:=]|(?<![A-Za-z])sk-[A-Za-z0-9_-]{20,}")),
        ("legacy construct name", re.compile(r"bank_" + "trust" + "sec")),
    ]


def validate(root: Path):
    findings = []
    root = root.resolve()
    for path in root.rglob("*"):
        rel = path.relative_to(root).as_posix()
        parts = set(path.relative_to(root).parts)
        if parts & SKIP_DIR_NAMES:
            continue
        if path.name == "review_only":
            findings.append({"type": "review-only material", "path": rel})
        if path.name in CACHE_NAMES:
            findings.append({"type": "runtime cache", "path": rel})
        if path.is_file() and path.suffix.lower() in TEMP_SUFFIXES:
            findings.append({"type": "temporary artifact", "path": rel})
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append({"type": "forbidden source or archive file", "path": rel})
        if path.is_file() and (path.suffix.lower() in TEXT_EXTS or path.name == ".gitignore"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for label, pattern in checks():
                if pattern.search(text):
                    findings.append({"type": label, "path": rel})
    return findings


def main():
    parser = argparse.ArgumentParser(description="Validate a release tree before packaging.")
    parser.add_argument("path")
    args = parser.parse_args()
    root = Path(args.path).resolve()
    findings = validate(root)
    print(json.dumps({"path": str(root), "findings": findings, "passed": not findings}, ensure_ascii=False, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
