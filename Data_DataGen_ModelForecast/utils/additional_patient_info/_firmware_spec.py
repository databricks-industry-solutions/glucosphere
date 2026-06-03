# Databricks notebook source
# MAGIC %md
# MAGIC # Firmware era + device-error model — single source of truth
# MAGIC
# MAGIC The fleet rolls a single firmware sequence `3.14 → 4.0 → 4.0.3 → 4.1` whose
# MAGIC era boundaries are a pure function of the incident-window `cfg` params (the same
# MAGIC params `05`/`06` use to place the two calibration incidents). Every component that
# MAGIC needs firmware — the device-telemetry generator (`Create Raw Device Data`), the
# MAGIC incident simulation (`05`/`06`), and the sanity gate — `%run`s this spec so they
# MAGIC compute the **identical** era for every reading. Mirrors `_device_model_spec`.
# MAGIC
# MAGIC ## Why each firmware also carries a device-error σ
# MAGIC
# MAGIC `glucose_observed = glucose_true + measurement_noise(firmware) + acute_fault`. Real
# MAGIC CGMs are not perfect: they have a measurement error (MARD ≈ 9% of the reading). We
# MAGIC model that as **zero-mean** noise whose magnitude (σ, mg/dL) depends on the firmware:
# MAGIC the buggy rollout (`4.0`/`4.0.3`) ships *degraded* (σ≈11 ≈ MARD-9%), the good
# MAGIC versions (`3.14`/`4.1`) are tight (σ≈3–4 ≈ MARD-3%). On top of that, the two acute
# MAGIC calibration incidents add a **systematic** ±40 mg/dL bias (handled in `05`/`06`).
# MAGIC
# MAGIC Because the per-firmware noise is **zero-mean**, it raises the device-error heatmap
# MAGIC metric `mean|observed − true|` (clean cell → 0.8·σ) into a real green→amber→red
# MAGIC gradient **without shifting** the clinical mean — OOR / TIR / High-Risk move <1%
# MAGIC (verified by simulation on the real glucose distribution). The noise is a
# MAGIC **deterministic** function of `(patient_id, time)` — no `rand()`/`np.random`, so it
# MAGIC is stable across every run and workspace, exactly like `device_model`.

# COMMAND ----------

from datetime import datetime, timedelta

# Canonical firmware sequence (chronological). STRING (not float) so `4.0.3` is expressible;
# the column is string-compared/displayed everywhere downstream (app CASTs to string).
FIRMWARE_VERSIONS = ["3.14", "4.0", "4.0.3", "4.1"]

# Per-firmware device-error σ (mg/dL) as a (start, end) RAMP across the firmware's life.
# Real devices degrade *gradually*, so the measurement-error σ climbs over a firmware
# version's days rather than sitting flat — this is what turns the heatmap from green+red
# "binary" into a true green→amber→red gradient (heatmap cell ≈ 0.8·σ on the 0→40 scale).
#   clean 3.14/4.1 ≈ flat 2–4  (MARD ~2–3%)                          -> green
#   buggy 4.0   ramps 6 → 15  (ships ok-ish, degrades over its life) -> green→amber
#   buggy 4.0.3 ramps 12 → 18 (hotfix shipped already-degraded, worsens) -> amber
# Noise is zero-mean, so this raises mean|observed−true| (the heatmap metric) WITHOUT moving
# the clinical mean; eras are short (≤2 days) so the high-σ tail applies to a fraction of the
# week → aggregate OOR/TIR shift stays small (re-verified by simulation before each re-run).
FIRMWARE_ERROR_SIGMA_RAMP = {
    "3.14":  (3.0, 4.0),
    "4.0":   (6.0, 15.0),
    # 4.0.3 (the hotfix) STARTS near-clean — accuracy briefly recovers almost to baseline when
    # the patch ships, so the fleet error visibly dips between the two incidents ("looked
    # fixed") — then re-degrades as the patch fails to actually fix the calibration. Tells the
    # "hotfix tried, looked fixed, failed" story.
    "4.0.3": (4.0, 17.0),
    "4.1":   (2.0, 3.0),
}
assert set(FIRMWARE_ERROR_SIGMA_RAMP) == set(FIRMWARE_VERSIONS), \
    "every firmware version must have a device-error σ ramp exactly once"
# Single-number midpoint σ (back-compat for any consumer that wants one value, e.g. docs/tests).
FIRMWARE_ERROR_SIGMA = {fw: (lo + hi) / 2.0 for fw, (lo, hi) in FIRMWARE_ERROR_SIGMA_RAMP.items()}

# Faulty rollouts (the demo's "which versions to recall"): the two with degraded σ.
FAULTY_FIRMWARES = ["4.0", "4.0.3"]
CLEAN_FIRMWARES  = ["3.14", "4.1"]
assert sorted(FAULTY_FIRMWARES + CLEAN_FIRMWARES) == sorted(FIRMWARE_VERSIONS), \
    "every firmware must be classified faulty / clean exactly once"


def firmware_eras(cfg):
    """Contiguous, **day-aligned** firmware eras as `[(version, start_iso, end_iso), ...]`.

    Day-aligned (midnight boundaries) so each firmware spans whole days AND each calibration
    incident sits *fully inside* its firmware's era (the rollout precedes the fault, which is
    how it works in the field) — never on a boundary instant. With `incident_start_day=2` and
    `second_incident_start_day=5` this yields: 3.14 = days 0–1, 4.0 = days 2–3 (contains
    window-1), 4.0.3 = days 4–5 (contains window-2), 4.1 = day 6+ (recall). Derived purely
    from the incident `cfg` params (single source of truth for telemetry + 05 + the gate)."""
    d0 = datetime.fromisoformat(str(cfg.demo_week_start))
    def iso(days):
        return (d0 + timedelta(days=days)).isoformat() + "+00:00"
    far = "9999-12-31T23:59:59+00:00"
    return [
        ("3.14",  iso(0),                               iso(cfg.incident_start_day)),          # data start → 4.0 rollout
        ("4.0",   iso(cfg.incident_start_day),          iso(cfg.second_incident_start_day - 1)),  # contains window-1
        ("4.0.3", iso(cfg.second_incident_start_day - 1), iso(cfg.second_incident_start_day + 1)),  # contains window-2
        ("4.1",   iso(cfg.second_incident_start_day + 1), far),                                # recall / fixed
    ]


def firmware_boundaries(cfg):
    """The 3 firmware-era transition timestamps (rollout→4.0, patch→4.0.3, recall→4.1),
    derived from `firmware_eras`. Kept for back-compat with callers that want the boundaries."""
    eras = firmware_eras(cfg)
    return eras[1][1], eras[2][1], eras[3][1]


def firmware_version_case_sql(cfg, time_col: str = "time") -> str:
    """Spark-SQL CASE mapping `time_col` to the firmware version string, from `firmware_eras`.
    Identical in telemetry + 05 + 06 + the sanity gate (one source of truth)."""
    whens = "\n".join(
        f"        WHEN {time_col} < TIMESTAMP('{end}') THEN '{fw}'"
        for fw, _start, end in firmware_eras(cfg)[:-1]
    )
    return f"CASE\n{whens}\n        ELSE '{firmware_eras(cfg)[-1][0]}'\n    END"


def firmware_sigma_case_sql(cfg, time_col: str = "time") -> str:
    """Spark-SQL CASE mapping `time_col` to the firmware's device-error σ (mg/dL), **ramped**
    linearly from the version's start-σ to end-σ across its era (so error grows over the
    firmware's life). Uses the SAME `firmware_eras`, so the σ a reading gets always matches
    the firmware it is labelled with — they can never drift."""
    def ramp(fw, start, end):
        lo, hi = FIRMWARE_ERROR_SIGMA_RAMP[fw]
        # position in [0,1] across the era; for the open-ended final era the far-future `end`
        # makes position ≈ 0 → effectively flat at `lo` (clean recall doesn't degrade).
        pos = (f"least(1.0, greatest(0.0, "
               f"(unix_timestamp({time_col}) - unix_timestamp(TIMESTAMP('{start}'))) / "
               f"(unix_timestamp(TIMESTAMP('{end}')) - unix_timestamp(TIMESTAMP('{start}')))))")
        return f"({lo} + ({hi} - {lo}) * {pos})"
    eras = firmware_eras(cfg)
    whens = "\n".join(
        f"        WHEN {time_col} < TIMESTAMP('{end}') THEN {ramp(fw, start, end)}"
        for fw, start, end in eras[:-1]
    )
    fw_last, start_last, end_last = eras[-1]
    return f"CASE\n{whens}\n        ELSE {ramp(fw_last, start_last, end_last)}\n    END"


def device_noise_expr_sql(id_col: str = "patient_id", time_col: str = "time",
                          sigma_sql: str = None) -> str:
    """Spark-SQL expression for a DETERMINISTIC, zero-mean Gaussian measurement-noise term
    (mg/dL) that is a pure function of (id_col, time_col) — so it is identical across every
    run/workspace (the determinism rule), unlike `rand()`/`randn()` which depend on
    partition layout.

    Construction: two independent uniforms in (0,1) from md5 hashes of (id|time|salt) →
    Box-Muller standard-normal z → scaled by the per-firmware σ. `sigma_sql` is a SQL
    scalar expression for σ (pass `firmware_sigma_case_sql(cfg)`)."""
    if sigma_sql is None:
        raise ValueError("device_noise_expr_sql requires sigma_sql (e.g. firmware_sigma_case_sql(cfg))")

    def _u(salt):
        # md5(id|time|salt) -> first 8 hex -> int -> uniform in (0,1), open interval
        # (+1 / +1.0 avoids exactly 0 so ln() is finite in Box-Muller).
        h = (f"pmod(cast(conv(substr(md5(concat(cast({id_col} as string), '|', "
             f"cast({time_col} as string), '|{salt}')), 1, 8), 16, 10) as bigint), 1000000)")
        return f"(({h}) + 1) / 1000001.0"

    u1, u2 = _u("n1"), _u("n2")
    z = f"sqrt(-2.0 * ln({u1})) * cos(2.0 * pi() * {u2})"   # ~ N(0,1)
    return f"({z}) * ({sigma_sql})"
