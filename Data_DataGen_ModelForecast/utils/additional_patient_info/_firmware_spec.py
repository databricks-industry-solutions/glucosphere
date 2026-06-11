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
# MAGIC ## Device-error σ — device-model-gated, two-pulse
# MAGIC
# MAGIC `glucose_observed = glucose_true + measurement_noise(model, time) + acute_fault`. Real
# MAGIC CGMs are not perfect: they have a measurement error (MARD ≈ 9% of the reading). We model
# MAGIC that as **zero-mean** noise whose magnitude (σ, mg/dL) depends on the device MODEL and time:
# MAGIC faulty models (`Alpha`/`Gamma`/`Beta`/`Delta`) rise to σ≈10 (MARD ~8%) into each of the two
# MAGIC calibration incidents then recover gradually; clean control models (`Epsilon`/`Zeta`) stay
# MAGIC flat σ≈3 (MARD ~3%). On top of that, the two acute calibration incidents add a
# MAGIC **systematic** ±40 mg/dL bias on the faulty-model cohorts (handled in `05`/`06`).
# MAGIC
# MAGIC Because the noise is **zero-mean**, it raises the device-error heatmap
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

# Device-error σ (mg/dL) — DEVICE-MODEL-GATED, TWO-PULSE model (refined 2026-06-10).
# σ is NOT a flat per-firmware value. Two things shape it (see firmware_sigma_case_sql):
#   1. WHICH device models — only FAULTY models (Alpha/Gamma/Beta/Delta) carry elevated σ;
#      CLEAN models (Epsilon/Zeta) stay at σ≈SIGMA_CLEAN at ALL times (their hardware tolerates
#      the buggy firmware) → they are the flat "control" cohort.
#   2. WHEN — for a faulty model, σ rises into each of the TWO calibration incidents, holds
#      across the fault window, then RECOVERS GRADUALLY (affected devices take time to recover).
#      → two separable buggy periods with a dip between ("hotfix looked fixed, then failed"),
#      not one continuous box, and not the old within-era drift.
# firmware_VERSION stays fleet-wide/time-based (every model rolls 3.14→4.0→4.0.3→4.1) so the
# device×firmware heatmap stays COMPLETE — only σ is model-gated (the 2026-06-02 c5713a0 fix
# made firmware fleet-wide precisely so clean models aren't blank on 4.0/4.0.3 — we keep that).
# Noise is zero-mean → raises mean|observed−true| (heatmap metric ≈ 0.8·σ) WITHOUT moving the
# clinical mean. σ_peak has no high tail → the forecaster stays realistic (above naive ~9).
SIGMA_CLEAN = 3.0                  # baseline σ: clean models always; faulty models between/around pulses. MARD ~2–3%.
SIGMA_PEAK  = 10.0                 # faulty-model σ at an incident peak. MARD ~8% (degraded device).
SIGMA_ONSET_HOURS = 4.0            # fast rise so σ reaches SIGMA_PEAK by the incident onset (fault lands on full σ).
SIGMA_RECOVERY_TAU_HOURS = 12.0    # exp recovery time-constant after each incident (~3τ ≈ 36h back toward clean).
# Legacy single-value σ map (kept only for any doc/test consumer; the pulse model does NOT use it).
FIRMWARE_ERROR_SIGMA = {"3.14": SIGMA_CLEAN, "4.0": SIGMA_PEAK, "4.0.3": SIGMA_PEAK, "4.1": SIGMA_CLEAN}

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


def incident_onsets(cfg):
    """The two calibration incidents as `[(onset_iso, hold_end_iso), ...]`, from the SAME cfg
    params 05/06 use to place the windows — so the σ pulse a reading gets always lines up with
    the acute ±40 fault. Onset = demo_week_start + start_day + start_hour; hold_end = + duration."""
    d0 = datetime.fromisoformat(str(cfg.demo_week_start))
    def pair(day, hour, dur_min):
        o = d0 + timedelta(days=day, hours=hour)
        h = o + timedelta(minutes=dur_min)
        return o.isoformat() + "+00:00", h.isoformat() + "+00:00"
    return [
        pair(cfg.incident_start_day, cfg.incident_start_hour, cfg.incident_duration_min),
        pair(cfg.second_incident_start_day, cfg.second_incident_start_hour,
             getattr(cfg, "second_incident_duration_min", cfg.incident_duration_min)),
    ]


def firmware_sigma_case_sql(cfg, time_col: str = "time", model_sql: str = None,
                            clean_models=None) -> str:
    """Spark-SQL scalar expression for the device-error σ (mg/dL) — DEVICE-MODEL-GATED, TWO-PULSE.

    Faulty models: σ = SIGMA_CLEAN baseline, rising to SIGMA_PEAK into each of the two incidents
    (linear rise over SIGMA_ONSET_HOURS, so σ is at PEAK by the fault onset), holding across the
    fault window, then decaying exponentially (SIGMA_RECOVERY_TAU_HOURS) back toward clean — two
    separable buggy periods with gradual recovery + a dip between.
    Clean models (in `clean_models`, e.g. CLEAN_MODELS): flat SIGMA_CLEAN at all times.

    `model_sql`  — SQL expr yielding the device model (e.g. `device_model_case_sql('patient_id')`).
                   If None (or `clean_models` empty), NO gating: every reading is treated as faulty.
    `clean_models` — list of control model names that stay flat (e.g. CLEAN_MODELS)."""
    ut = f"unix_timestamp({time_col})"
    onset_s = SIGMA_ONSET_HOURS * 3600.0
    tau_s = SIGMA_RECOVERY_TAU_HOURS * 3600.0

    def pulse_shape(o_iso, h_iso):
        # 0→1 fast linear rise over [onset-SIGMA_ONSET_HOURS, onset]; hold 1 over [onset, hold_end];
        # exp decay after hold_end. greatest(0,…) clamps the pre-rise region to 0.
        uo = f"unix_timestamp(TIMESTAMP('{o_iso}'))"
        uh = f"unix_timestamp(TIMESTAMP('{h_iso}'))"
        return (
            f"greatest(0.0, CASE"
            f" WHEN {ut} < {uo} - {onset_s} THEN 0.0"
            f" WHEN {ut} < {uo} THEN ({ut} - ({uo} - {onset_s})) / {onset_s}"
            f" WHEN {ut} < {uh} THEN 1.0"
            f" ELSE exp(-({ut} - {uh}) / {tau_s})"
            f" END)"
        )

    shapes = [pulse_shape(o, h) for o, h in incident_onsets(cfg)]
    pulse_max = shapes[0] if len(shapes) == 1 else f"greatest({', '.join(shapes)})"
    faulty_sigma = f"({SIGMA_CLEAN} + ({SIGMA_PEAK} - {SIGMA_CLEAN}) * {pulse_max})"

    clean_list = ", ".join(f"'{m}'" for m in (clean_models or []))
    if model_sql is None or not clean_list:
        return faulty_sigma
    # Clean models tolerate the buggy firmware → flat baseline; faulty models take the pulses.
    return f"CASE WHEN ({model_sql}) IN ({clean_list}) THEN {SIGMA_CLEAN} ELSE {faulty_sigma} END"


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
