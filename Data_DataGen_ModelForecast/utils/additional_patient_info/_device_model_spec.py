# Databricks notebook source
# MAGIC %md
# MAGIC # Device-model assignment — single source of truth
# MAGIC
# MAGIC `device_model` is a **fixed per-device property derived purely from `patient_id`**
# MAGIC via an md5 hash bucket. Every component that needs it — the incident simulation
# MAGIC (`05`), the patient registry, and the device-telemetry generator — `%run`s this
# MAGIC spec and computes the **identical** value. Because it is a pure function of the id:
# MAGIC
# MAGIC * no read-ordering dependency (no component has to wait for another's table),
# MAGIC * no random seed / shuffle (stable across every run and workspace),
# MAGIC * no fallback path (nothing to silently diverge).
# MAGIC
# MAGIC This replaces three previously-independent random assignments (registry
# MAGIC `np.random.choice`, telemetry `rand(seed=42)`, and `05`'s registry-read-or-random
# MAGIC fallback) that disagreed with each other and broke the device→bias-direction story.

# COMMAND ----------

# Canonical model list + population weights (aligned by index — keep in sync).
DEVICE_MODELS = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta"]
DEVICE_MODEL_WEIGHTS = [0.22, 0.22, 0.19, 0.16, 0.13, 0.08]
assert len(DEVICE_MODELS) == len(DEVICE_MODEL_WEIGHTS), "models/weights length mismatch"
assert abs(sum(DEVICE_MODEL_WEIGHTS) - 1.0) < 1e-9, "device_model weights must sum to 1.0"

# Calibration-bias cohorts (the demo story). 05 draws its incident cohorts from these
# pools; the clinical-plausibility sanity gate asserts the gold data honors them.
POS_BIAS_MODELS = ["Alpha", "Gamma"]   # over-read  (+bias), incident window 1
NEG_BIAS_MODELS = ["Beta", "Delta"]    # under-read (-bias), incident window 2
CLEAN_MODELS    = ["Epsilon", "Zeta"]  # control — never assigned an incident
assert sorted(POS_BIAS_MODELS + NEG_BIAS_MODELS + CLEAN_MODELS) == sorted(DEVICE_MODELS), \
    "every device_model must be classified as positive / negative / clean exactly once"

_HASH_BUCKETS = 10000  # md5 -> integer -> bucket resolution


def device_model_case_sql(id_col: str = "patient_id") -> str:
    """Spark-SQL expression mapping `id_col` deterministically to a device_model,
    weighted by DEVICE_MODEL_WEIGHTS.

    Pure function of the id: md5(id) -> first 8 hex digits -> integer -> bucket in
    [0, _HASH_BUCKETS) -> cumulative-weight band. One SQL expression over Spark's
    md5(), so it is identical in every notebook/engine that uses it. Thresholds are
    derived from DEVICE_MODEL_WEIGHTS (the single source), never hand-typed.
    """
    bucket = (f"pmod(cast(conv(substr(md5(cast({id_col} as string)), 1, 8), 16, 10) "
              f"as bigint), {_HASH_BUCKETS})")
    cum, whens = 0.0, []
    for model, w in zip(DEVICE_MODELS[:-1], DEVICE_MODEL_WEIGHTS[:-1]):
        cum += w
        whens.append(f"WHEN {bucket} < {int(round(cum * _HASH_BUCKETS))} THEN '{model}'")
    whens_sql = "\n        ".join(whens)
    return f"CASE\n        {whens_sql}\n        ELSE '{DEVICE_MODELS[-1]}'\n    END"
