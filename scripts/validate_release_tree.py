import argparse
import json
import re
import sys
from pathlib import Path

TEXT_EXTS = {".md", ".py", ".json", ".csv", ".ipynb", ".txt", ".gitignore", ".yml", ".yaml"}
CACHE_NAMES = {".pytest_cache", "__pycache__"}
TEMP_SUFFIXES = {".pyc", ".log", ".tmp"}


def checks():
    student_label = "\u5b66" + "\u53f7"
    respondent_ip = "\u6765\u81ea" + "IP"
    submission_time = "\u63d0\u4ea4" + "\u7b54\u5377" + "\u65f6\u95f4"
    source_detail = "\u6765\u6e90" + "\u8be6\u60c5"
    return [
        ("absolute user path", re.compile(r"C:" + re.escape("\\") + r"Users|Admin" + "istrator")),
        ("desktop path", re.compile(re.escape("\\") + r"Desk" + "top" + re.escape("\\"))),
        ("education identifier marker", re.compile(student_label + r"|" + "student" + r"\s*" + "id" + r"|" + "student" + "_" + "id", re.I)),
        ("survey ip metadata", re.compile(respondent_ip + r"|respondent\s*ip", re.I)),
        ("survey time metadata", re.compile(submission_time + r"|submission\s*timestamp", re.I)),
        ("survey source metadata", re.compile(source_detail + r"|source\s*detail", re.I)),
        ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
        ("credential", re.compile(r"(?i)(api[_-]?key|password|secret|token)\s*[:=]|(?<![A-Za-z])sk-[A-Za-z0-9_-]{20,}")),
    ]

def validate(root: Path):
    findings = []
    for path in root.rglob("*"):
        rel = path.relative_to(root).as_posix()
        if path.name in CACHE_NAMES:
            findings.append({"type": "runtime cache", "path": rel})
        if path.is_file() and path.suffix.lower() in TEMP_SUFFIXES:
            findings.append({"type": "temporary artifact", "path": rel})
        if path.is_file() and path.suffix.lower() in TEXT_EXTS:
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
