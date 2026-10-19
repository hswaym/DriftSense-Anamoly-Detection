# DriftSense — Reproducibility & Execution Protocol

This document establishes the end-to-end execution workflow for DriftSense across local development and Google Colab environments.

---

## 1. Local Environment Workflow (Antigravity Machine)

The local machine is strictly reserved for code editing, unit testing, schema verification, and notebook compilation. Heavy dataset downloads and model training runs are deferred to Google Colab.

### 1.1 Running Unit Tests
Execute the test suite against the built-in synthetic fixtures ($\le 50$ rows):
```bash
pytest -v
```
Expected output: All 12 unit tests pass with exit code `0`.

### 1.2 Compiling Deterministic Notebooks
Notebooks are compiled from templates in `notebooks/templates/` to `notebooks/generated/`:
```bash
python scripts/build_notebooks.py
```
*Note: Hand edits to files in `notebooks/generated/` will be overwritten.*

### 1.3 Verifying Colab Artifact Manifests
When a Colab run completes, download the run folder containing `manifest.json` and verify its integrity locally:
```bash
driftsense verify-manifest runs/<run_id>
```
Expected output: `PASS: Manifest verified successfully at 'runs/<run_id>'.` (Exit code `0`).

---

## 2. Google Colab Execution Workflow

All model training, full-scale dataset downloads, exploratory data analysis, and benchmark evaluations take place on Google Colab.

### Step-by-Step Colab Instructions:
1. Open Google Colab: [https://colab.research.google.com/](https://colab.research.google.com/)
2. Upload or open the generated notebook:
   `notebooks/generated/01_acquire_validate.ipynb`
3. Run all cells sequentially.
4. **Expected Cell Outputs**:
   - Cell 1: Clones repository at pinned commit `5e57c0a` and installs `driftsense`.
   - Cell 2: Runs `driftsense hwcheck` and prints CPU/RAM/Disk diagnostics.
   - Cell 3: Creates timestamped run directory: `runs/<run_id>/`.
   - Cell 4: Idempotently downloads `data/raw/focus_sample_10000.csv` and verifies SHA256 checksum (`0bf58b73123294c4476b648e647cad842935036f67dc4e9a2cc4a6d7497cc2e3`).
   - Cell 5: Executes `driftsense validate` and emits `data_quality_report.json`.
   - Cell 6: Writes `manifest.json` and validates that all artifact hashes match.
5. **Artifact Handoff**:
   - Download the `runs/<run_id>/` folder containing `manifest.json` and `data_quality_report.json` back to your local repository for Phase 3 verification.
