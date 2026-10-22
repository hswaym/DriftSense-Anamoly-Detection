"""Secret and sensitive credential scan for Phase 0 forensic audit.

Scans repo files for accidentally tracked tokens, passwords, keys, or credentials.
Reports matching file paths only (never values).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def scan_secrets() -> list[dict]:
    keywords = [
        r"(?i)api[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_\-]{8,}['\"]",
        r"(?i)secret[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_\-]{8,}['\"]",
        r"(?i)bearer\s+[A-Za-z0-9_\-\.]{16,}",
        r"(?i)private[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_\-]{8,}['\"]",
        r"(?i)password\s*[:=]\s*['\"][^'\"]{6,}['\"]",
        r"ghp_[A-Za-z0-9]{36}",
        r"AIza[0-9A-Za-z-_]{35}",
    ]
    compiled = [re.compile(p) for p in keywords]

    ignored_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
    suspicious = []

    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for f in files:
            if f.endswith((".py", ".yaml", ".yml", ".json", ".md", ".toml", ".txt", ".csv")):
                path = Path(root) / f
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                    for c in compiled:
                        if c.search(text):
                            suspicious.append({"file": str(path.relative_to(REPO_ROOT))})
                            break
                except OSError:
                    continue

    return suspicious


if __name__ == "__main__":
    findings = scan_secrets()
    print(f"Secret scan completed. Suspicious files found: {len(findings)}")
    for f in findings:
        print(f"  - {f['file']}")
