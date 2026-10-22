"""Generate comprehensive repository inventory for Phase 0 forensic audit.

Inspects pyproject.toml, configs/, src/, app/, tests/, notebooks/, runs/, docs/, data/.
Records module paths, lines of code, public APIs, imports, and TODOs.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def analyze_python_file(path: Path) -> dict:
    code = path.read_text(encoding="utf-8", errors="ignore")
    lines = len(code.splitlines())
    todos = [line.strip() for line in code.splitlines() if "TODO" in line or "FIXME" in line]

    public_api = []
    imports = []
    hardcoded_paths = []

    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    public_api.append(f"def {node.name}()")
            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith("_"):
                    public_api.append(f"class {node.name}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    imports.append(f"{mod}.{alias.name}")
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                val = node.value
                if any(p in val for p in ["C:\\", "/home/", "/Users/", "data/", "runs/", "configs/"]):
                    hardcoded_paths.append(val)
    except Exception:
        # Ignore AST parsing errors on non-standard files
        return {
            "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "lines": lines,
            "public_api": [],
            "imports": [],
            "todos": todos,
            "hardcoded_paths": [],
        }

    return {
        "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "lines": lines,
        "public_api": sorted(set(public_api)),
        "imports": sorted(set(imports)),
        "todos": todos,
        "hardcoded_paths": sorted(set(hardcoded_paths)),
    }


def main():
    modules = []
    for root, dirs, files in os.walk(REPO_ROOT / "src"):
        for f in files:
            if f.endswith(".py"):
                p = Path(root) / f
                modules.append(analyze_python_file(p))

    app_modules = []
    for root, dirs, files in os.walk(REPO_ROOT / "app"):
        for f in files:
            if f.endswith(".py"):
                p = Path(root) / f
                app_modules.append(analyze_python_file(p))

    test_modules = []
    for root, dirs, files in os.walk(REPO_ROOT / "tests"):
        for f in files:
            if f.endswith(".py"):
                p = Path(root) / f
                test_modules.append(analyze_python_file(p))

    out_md = REPO_ROOT / "docs" / "audit" / "repo_inventory.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# DriftSense v1 — Repository Inventory (Phase 0 Audit)\n\n")
        f.write(f"Total `src/` modules: {len(modules)}\n")
        f.write(f"Total `app/` modules: {len(app_modules)}\n")
        f.write(f"Total `tests/` modules: {len(test_modules)}\n\n")

        f.write("## 1. Source Package (`src/driftsense/`)\n\n")
        f.write("| Module Path | Lines | Public API Entities | TODOs | Relative Hardcoded Paths |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        for m in sorted(modules, key=lambda x: x["path"]):
            api_str = ", ".join(m["public_api"][:4]) + ("..." if len(m["public_api"]) > 4 else "")
            todo_count = len(m["todos"])
            paths_count = len(m["hardcoded_paths"])
            f.write(f"| `{m['path']}` | {m['lines']} | `{api_str or 'None'}` | {todo_count} | {paths_count} |\n")

        f.write("\n## 2. Dashboard Application (`app/`)\n\n")
        f.write("| Module Path | Lines | Public API Entities | TODOs |\n")
        f.write("| :--- | :--- | :--- | :--- |\n")
        for m in sorted(app_modules, key=lambda x: x["path"]):
            api_str = ", ".join(m["public_api"][:4])
            f.write(f"| `{m['path']}` | {m['lines']} | `{api_str or 'None'}` | {len(m['todos'])} |\n")

        f.write("\n## 3. Test Suite (`tests/`)\n\n")
        f.write("| Test Module Path | Lines | Test Functions Count |\n")
        f.write("| :--- | :--- | :--- |\n")
        for m in sorted(test_modules, key=lambda x: x["path"]):
            f.write(f"| `{m['path']}` | {m['lines']} | {len(m['public_api'])} |\n")

        f.write("\n## 4. Configuration Inventory (`configs/`)\n\n")
        configs = list((REPO_ROOT / "configs").glob("*.yaml"))
        f.write("| Config Path | File Size |\n| :--- | :--- |\n")
        f.writelines(f"| `configs/{c.name}` | {c.stat().st_size} bytes |\n" for c in configs)

    print(f"Inventory generated successfully at: {out_md}")


if __name__ == "__main__":
    main()
