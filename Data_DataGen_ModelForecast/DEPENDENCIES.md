# Dependencies — Data_DataGen_ModelForecast (license inventory)

Canonical dependency + license inventory for the data-generation / modeling notebooks
(kept as a dedicated file so license audits have one stable per-area location; see also
[`App/DEPENDENCIES.md`](../App/DEPENDENCIES.md) for the app's frontend/backend inventory).

**Python runtime:** notebooks run on Databricks Runtime (`spark_version` per the pipeline / job definition in `databricks.yml`) — the DBR provides the Python interpreter. Repo-root `scripts/` (e.g. `render_app_yaml.py`, `smoke_test.py`) run locally on Python 3.11 via `uv` (per `pyproject.toml requires-python>=3.10` + `.python-version`).

| Dependency | Where used | Why it’s used | License |
| --- | --- | --- | --- |
| [**pyspark**](https://github.com/apache/spark) | `01_*`, `02_*`, `03_*`, `04_*`, `05_*`, `06_*`, `utils/*` | Spark reads/writes, windowing, UC Delta tables | Apache-2.0 |
| [**pandas**](https://github.com/pandas-dev/pandas) | `02_*`, `03_*`, `04_*`, `05_*`, `06_*` | DataFrames for QC, feature engineering, analysis | BSD-3-Clause |
| [**numpy**](https://github.com/numpy/numpy) | `01_*`, `02_*`, `03_*`, `04_*`, `05_*`, `06_*` | Numeric ops, feature calculations | BSD-3-Clause |
| [**requests**](https://github.com/psf/requests) | `02_ingest_real_baseline.py`, `07_deploy_serving_endpoints.py`, `08_genie_ka_mas.py`, `09_grant_app_permissions.py` | Download HUPA-UCM dataset ZIP; call serving endpoints; create/PATCH Genie + KA + MAS endpoints via REST | Apache-2.0 |
| [**PyYAML**](https://github.com/yaml/pyyaml) (`yaml`) | `04_*`, `05_*`, `06_*`, `07_*` | Load `configs/baseline_config.yaml` | MIT |
| [**mlflow**](https://github.com/mlflow/mlflow) | `04_*`, `05_*`, `06_*`, `07_*` | Experiment tracking, model registry, inference helpers | Apache-2.0 |
| [**xgboost**](https://github.com/dmlc/xgboost) | `04_*`, `05_*`, `06_*` (+ `%pip install xgboost`) | Forecasting model training/inference | Apache-2.0 |
| [**scikit-learn**](https://github.com/scikit-learn/scikit-learn) (`sklearn`) | `04_*`, `05_*`, `06_*` | Metrics (e.g., MAE) and utilities | BSD-3-Clause |
| [**scipy**](https://github.com/scipy/scipy) | `03_*`, `04_*` | Distribution comparison metrics (KS, Wasserstein), stats | BSD-3-Clause |
| [**matplotlib**](https://github.com/matplotlib/matplotlib) | `03_*`, `04_*`, `05_*`, `06_*` | Visualization | PSF-based (Matplotlib license) |
| [**seaborn**](https://github.com/mwaskom/seaborn) | `04_*`, `05_*`, `06_*` | Visualization styling + distributions | BSD-3-Clause |
| [**optuna**](https://github.com/optuna/optuna) | `04_pseudo_data_forecast_modeling.py` | Optional hyperparameter tuning | MIT |
| [**databricks-sdk**](https://github.com/databricks/databricks-sdk-py) | `07_deploy_serving_endpoints.py` | Create/update Model Serving endpoints via API | Apache-2.0 |
| [**psutil**](https://github.com/giampaolo/psutil) | `04_pseudo_data_forecast_modeling.py` (`%pip install`) | MLflow system metrics logging (CPU/memory) | BSD-3-Clause |
| [**nvidia-ml-py**](https://pypi.org/project/nvidia-ml-py/) | `04_pseudo_data_forecast_modeling.py` (`%pip install`) | NVML bindings (provides `pynvml` import) — required by MLflow's `GPUMonitor` for GPU stats on g5.12xlarge / A10G clusters; silently skipped if absent. Supersedes deprecated `nvidia-ml-py3`. | BSD-3-Clause |
| [**alembic**](https://github.com/sqlalchemy/alembic) | `04_pseudo_data_forecast_modeling.py` (`%pip install`) | Optuna SQLite storage support (per notebook comments) | MIT |

## Note on package URLs and network reachability

GitHub source repos are linked on dependency names above where one exists. The `nvidia-ml-py` row links to PyPI because NVIDIA distributes the package only via PyPI (no public NVIDIA-hosted GitHub repo for these bindings). If your Databricks workspace or corporate network blocks direct egress to `pypi.org` / `files.pythonhosted.org` / `registry.npmjs.org` — a posture that accelerated after the [LiteLLM PyPI supply-chain compromise on 2026-03-24](https://blog.pypi.org/posts/2026-04-02-incident-report-litellm-telnyx-supply-chain-attack/) — install via your organization's internal pip proxy (Databricks workspaces commonly route through an Artifactory PyPI mirror) or pre-stage wheels in UC Volume. See [Databricks serverless egress-control docs](https://docs.databricks.com/aws/en/security/network/serverless-network-security/manage-network-policies) for allowlist configuration. Note also that Databricks ML Runtime (MLR) GPU images preinstall `nvidia-ml-py` from `18.x` onwards; plain DBR does not.
