"""Unit tests for DriftSense CLI commands and notebook compiler."""

from __future__ import annotations

from pathlib import Path

from driftsense.cli import main
from driftsense.runtime.manifest import ManifestBuilder
from scripts.build_notebooks import build_notebook


def test_cli_hwcheck(capsys):
    """Verify driftsense hwcheck CLI command."""
    code = main(["hwcheck", "--device", "cpu"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Platform:" in captured.out
    assert "CPU:" in captured.out


def test_cli_validate(tiny_focus_csv: Path, tmp_path: Path, capsys):
    """Verify driftsense validate CLI command."""
    out_rep = tmp_path / "cli_quality_report.json"
    code = main(
        ["validate", "--data", str(tiny_focus_csv), "--report-out", str(out_rep)]
    )
    assert code == 0
    assert out_rep.is_file()
    captured = capsys.readouterr()
    assert "Validation finished with status: PASSED" in captured.out


def test_cli_verify_manifest(tmp_path: Path):
    """Verify driftsense verify-manifest CLI command."""
    art = tmp_path / "artifact.txt"
    art.write_text("valid_content", encoding="utf-8")

    builder = ManifestBuilder(
        run_id="test_cli_run",
        phase="PHASE_3",
        stage="test",
        config_path="configs/data_focus.yaml",
        config_sha256="abc",
        seed=42,
    )
    builder.add_artifact(art)
    builder.save(tmp_path)

    code = main(["verify-manifest", str(tmp_path)])
    assert code == 0


def test_notebook_compiler_determinism(tmp_path: Path):
    """Verify notebook compiler produces deterministic output across multiple invocations."""
    tmpl_content = """# %% [markdown]
# # Test Title
# %%
import math
print(math.pi)
"""
    tmpl_file = tmp_path / "test.py.tmpl"
    tmpl_file.write_text(tmpl_content, encoding="utf-8")

    nb_file1 = tmp_path / "out1.ipynb"
    nb_file2 = tmp_path / "out2.ipynb"

    build_notebook(tmpl_file, nb_file1)
    build_notebook(tmpl_file, nb_file2)

    assert nb_file1.read_text(encoding="utf-8") == nb_file2.read_text(encoding="utf-8")
