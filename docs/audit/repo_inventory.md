# DriftSense v1 — Repository Inventory (Phase 0 Audit)

Total `src/` modules: 46
Total `app/` modules: 8
Total `tests/` modules: 19

## 1. Source Package (`src/driftsense/`)

| Module Path | Lines | Public API Entities | TODOs | Relative Hardcoded Paths |
| :--- | :--- | :--- | :--- | :--- |
| `src/driftsense/__init__.py` | 3 | `None` | 0 | 0 |
| `src/driftsense/attribute/__init__.py` | 18 | `None` | 0 | 0 |
| `src/driftsense/attribute/base.py` | 170 | `class BaseAttributor, def fit(), def get_metadata(), def load()...` | 0 | 0 |
| `src/driftsense/attribute/correlation.py` | 116 | `class TemporalCorrelationAttributor, def fit(), def rank()` | 0 | 0 |
| `src/driftsense/attribute/prior_baseline.py` | 79 | `class ClassPriorAttributor, def fit(), def rank()` | 0 | 0 |
| `src/driftsense/attribute/random_baseline.py` | 68 | `class RandomAttributor, def fit(), def rank()` | 0 | 0 |
| `src/driftsense/attribute/xgb_attributor.py` | 226 | `class XGBoostAttributor, def fit(), def rank()` | 0 | 0 |
| `src/driftsense/cli.py` | 1340 | `def cmd_acquire(), def cmd_attribute(), def cmd_clean(), def cmd_detect()...` | 0 | 14 |
| `src/driftsense/data/__init__.py` | 19 | `None` | 0 | 0 |
| `src/driftsense/data/acquire.py` | 90 | `def acquire_dataset()` | 0 | 0 |
| `src/driftsense/data/aggregate.py` | 129 | `def aggregate_to_canonical_grain()` | 0 | 0 |
| `src/driftsense/data/clean.py` | 180 | `def clean_focus_data()` | 0 | 0 |
| `src/driftsense/data/schemas.py` | 86 | `None` | 0 | 0 |
| `src/driftsense/data/validate.py` | 183 | `def validate_dataset()` | 0 | 0 |
| `src/driftsense/detect/__init__.py` | 17 | `None` | 0 | 0 |
| `src/driftsense/detect/base.py` | 147 | `class BaseAnomalyDetector, def fit(), def get_metadata(), def load()...` | 0 | 0 |
| `src/driftsense/detect/iforest.py` | 142 | `class IsolationForestDetector, def fit(), def score()` | 0 | 0 |
| `src/driftsense/detect/ocsvm.py` | 129 | `class OneClassSVMDetector, def fit(), def score()` | 0 | 0 |
| `src/driftsense/detect/rolling_threshold.py` | 123 | `class RollingThresholdDetector, def fit(), def score()` | 0 | 0 |
| `src/driftsense/detect/zscore.py` | 121 | `class ZScoreDetector, def fit(), def score()` | 0 | 0 |
| `src/driftsense/eval/ablation.py` | 785 | `class AblationRunner, def evaluate_forecaster_seeds(), def hash_file_sha256(), def run_all()...` | 0 | 0 |
| `src/driftsense/eval/attribution_metrics.py` | 162 | `def evaluate_attribution_suite(), def multi_label_incident_metrics(), def taxonomy_confusion_matrix(), def top_1_accuracy()...` | 0 | 0 |
| `src/driftsense/eval/detection_metrics.py` | 250 | `def event_level_metrics(), def false_positive_rate(), def point_confusion_matrix(), def point_f1_score()...` | 0 | 0 |
| `src/driftsense/eval/final.py` | 539 | `class HashGuardError, def assert_config_hashes_frozen(), def compute_file_sha256(), def evaluate_final_test_set()...` | 0 | 8 |
| `src/driftsense/eval/metrics.py` | 145 | `def compute_all_metrics(), def mean_absolute_error(), def mean_absolute_percentage_error(), def mean_absolute_scaled_error()...` | 0 | 0 |
| `src/driftsense/eval/splits.py` | 187 | `class RollingOriginSplitter, class SplitInfo, def chronological_split(), def split()` | 0 | 0 |
| `src/driftsense/explain/__init__.py` | 31 | `None` | 0 | 0 |
| `src/driftsense/explain/consistency.py` | 178 | `def compute_cause_agreement(), def compute_explanation_stability()` | 0 | 0 |
| `src/driftsense/explain/importance.py` | 75 | `def compute_global_importance()` | 0 | 0 |
| `src/driftsense/explain/narrative.py` | 115 | `def synthesize_cost_narrative(), def validate_non_causal_text()` | 0 | 0 |
| `src/driftsense/explain/shap_explainer.py` | 295 | `class InstanceExplanation, class TreeSHAPExplainer, def explain(), def explain_instance()...` | 0 | 0 |
| `src/driftsense/features/builder.py` | 232 | `class FeaturePipeline, def build_features(), def fit(), def fit_transform()...` | 0 | 0 |
| `src/driftsense/features/events.py` | 120 | `def add_event_features()` | 0 | 0 |
| `src/driftsense/features/temporal.py` | 137 | `def add_calendar_features(), def add_lag_features(), def add_rolling_features()` | 0 | 0 |
| `src/driftsense/features/usage.py` | 85 | `def add_usage_features()` | 0 | 0 |
| `src/driftsense/forecast/base.py` | 132 | `class BaseForecaster, def fit(), def get_metadata(), def load()...` | 0 | 0 |
| `src/driftsense/forecast/naive.py` | 176 | `class MovingAverageForecaster, class SeasonalNaiveForecaster, def fit(), def predict()` | 0 | 0 |
| `src/driftsense/forecast/smoothing.py` | 86 | `class ExponentialSmoothingForecaster, def fit(), def predict()` | 0 | 0 |
| `src/driftsense/forecast/xgb.py` | 165 | `class XGBoostForecaster, def feature_names_(), def fit(), def predict()` | 0 | 0 |
| `src/driftsense/runtime/__init__.py` | 14 | `None` | 0 | 0 |
| `src/driftsense/runtime/config.py` | 42 | `def compute_file_sha256(), def load_config()` | 0 | 0 |
| `src/driftsense/runtime/hardware.py` | 60 | `def check_hardware(), def get_gpu_info()` | 0 | 0 |
| `src/driftsense/runtime/manifest.py` | 258 | `class ManifestBuilder, def add_artifact(), def add_dataset(), def add_metrics_file()...` | 0 | 2 |
| `src/driftsense/runtime/seed.py` | 26 | `def set_seed()` | 0 | 0 |
| `src/driftsense/synth/__init__.py` | 7 | `None` | 0 | 0 |
| `src/driftsense/synth/injector.py` | 178 | `class SyntheticInjector, def inject()` | 0 | 0 |

## 2. Dashboard Application (`app/`)

| Module Path | Lines | Public API Entities | TODOs |
| :--- | :--- | :--- | :--- |
| `app/loaders.py` | 262 | `def find_latest_run_for_phase(), def get_default_runs_dir(), def list_available_runs(), def load_ablation_data()` | 0 |
| `app/main.py` | 187 | `def main()` | 0 |
| `app/views/__init__.py` | 1 | `None` | 0 |
| `app/views/ablations.py` | 98 | `def render_ablations()` | 0 |
| `app/views/attribution.py` | 134 | `def render_attribution()` | 0 |
| `app/views/explainability.py` | 106 | `def render_explainability()` | 0 |
| `app/views/forecast_anomalies.py` | 111 | `def render_forecast_anomalies()` | 0 |
| `app/views/overview.py` | 175 | `def render_overview()` | 0 |

## 3. Test Suite (`tests/`)

| Test Module Path | Lines | Test Functions Count |
| :--- | :--- | :--- |
| `tests/conftest.py` | 102 | 2 |
| `tests/test_ablation_runner.py` | 184 | 7 |
| `tests/test_acquire_validate.py` | 84 | 3 |
| `tests/test_app_loaders.py` | 112 | 8 |
| `tests/test_attribution_metrics.py` | 99 | 4 |
| `tests/test_attributors.py` | 185 | 4 |
| `tests/test_clean.py` | 240 | 12 |
| `tests/test_cli.py` | 126 | 8 |
| `tests/test_detection_metrics.py` | 120 | 4 |
| `tests/test_detectors.py` | 156 | 4 |
| `tests/test_e2e_pipeline.py` | 230 | 2 |
| `tests/test_explain.py` | 209 | 7 |
| `tests/test_features.py` | 100 | 6 |
| `tests/test_final_eval.py` | 169 | 5 |
| `tests/test_forecast_interface.py` | 143 | 4 |
| `tests/test_injector.py` | 51 | 1 |
| `tests/test_leakage.py` | 226 | 6 |
| `tests/test_metrics.py` | 106 | 6 |
| `tests/test_runtime.py` | 94 | 5 |

## 4. Configuration Inventory (`configs/`)

| Config Path | File Size |
| :--- | :--- |
| `configs/ablation_focus.yaml` | 1221 bytes |
| `configs/attribute_focus.yaml` | 1131 bytes |
| `configs/clean_focus.yaml` | 821 bytes |
| `configs/data_focus.yaml` | 814 bytes |
| `configs/detect_focus.yaml` | 1390 bytes |
| `configs/explain_focus.yaml` | 1148 bytes |
| `configs/features_focus.yaml` | 720 bytes |
| `configs/forecast_focus.yaml` | 1112 bytes |
