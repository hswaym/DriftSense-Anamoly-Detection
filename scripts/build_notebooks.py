"""Deterministic compiler from notebook templates to .ipynb files.

Converts percent-formatted python templates (*.py.tmpl) in notebooks/templates/
into canonical Jupyter notebooks in notebooks/generated/.
Ensures two consecutive builds produce byte-for-byte identical SHA256 hashes.
"""

from __future__ import annotations

import json
from pathlib import Path


def parse_tmpl_to_cells(tmpl_content: str) -> list[dict]:
    """Parse percent-formatted python template into notebook cells."""
    lines = tmpl_content.splitlines(keepends=True)
    cells: list[dict] = []
    current_cell_type: str | None = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped == "# %% [markdown]":
            if current_cell_type is not None:
                cells.append(create_cell(current_cell_type, current_lines))
            current_cell_type = "markdown"
            current_lines = []
        elif stripped.startswith("# %%") and not stripped.startswith("# %% [markdown]"):
            if current_cell_type is not None:
                cells.append(create_cell(current_cell_type, current_lines))
            current_cell_type = "code"
            current_lines = []
        else:
            if current_cell_type is not None:
                current_lines.append(line)

    if current_cell_type is not None:
        cells.append(create_cell(current_cell_type, current_lines))

    return cells


def create_cell(cell_type: str, raw_lines: list[str]) -> dict:
    """Format cell dictionary."""
    clean_lines: list[str] = []
    if cell_type == "markdown":
        for line in raw_lines:
            # Strip leading comment '# ' or '#'
            if line.startswith("# "):
                clean_lines.append(line[2:])
            elif line.startswith("#\n") or line.strip() == "#":
                clean_lines.append("\n")
            else:
                clean_lines.append(line)
    else:
        clean_lines = raw_lines

    # Normalize trailing newlines on each element except the last
    formatted_source: list[str] = []
    for l in clean_lines:
        if not l.endswith("\n"):
            formatted_source.append(l + "\n")
        else:
            formatted_source.append(l)

    # Strip empty leading/trailing lines
    while formatted_source and formatted_source[0].strip() == "":
        formatted_source.pop(0)
    while formatted_source and formatted_source[-1].strip() == "":
        formatted_source.pop()

    if cell_type == "markdown":
        return {
            "cell_type": "markdown",
            "metadata": {},
            "source": formatted_source,
        }
    else:
        return {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": formatted_source,
        }


def build_notebook(template_path: Path, output_path: Path) -> Path:
    """Compile a single template into .ipynb format."""
    content = template_path.read_text(encoding="utf-8")
    cells = parse_tmpl_to_cells(content)

    nb = {
        "cells": cells,
        "metadata": {
            "language_info": {
                "name": "python",
                "version": "3",
            },
            "orig_nbformat": 4,
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Deterministic JSON serialization
    serialized = json.dumps(nb, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    output_path.write_text(serialized, encoding="utf-8", newline="\n")
    return output_path


def build_all_notebooks() -> list[Path]:
    """Compile all templates in notebooks/templates/ to notebooks/generated/."""
    tmpl_dir = Path("notebooks/templates")
    out_dir = Path("notebooks/generated")
    out_dir.mkdir(parents=True, exist_ok=True)

    built: list[Path] = []
    for tmpl in sorted(tmpl_dir.glob("*.py.tmpl")):
        stem = tmpl.stem.replace(".py", "")
        out_nb = out_dir / f"{stem}.ipynb"
        build_notebook(tmpl, out_nb)
        built.append(out_nb)
        print(f"Compiled {tmpl} -> {out_nb}")

    return built


if __name__ == "__main__":
    build_all_notebooks()
