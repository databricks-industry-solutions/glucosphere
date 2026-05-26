# Synth E2E Validation Findings — 2026-05-26

> **Audience:** glucosphere maintainers (May, Justin, Morgan) + anyone reviewing or extending the synthetic baseline path.
>
> **Status:** Two latent bugs surfaced + fixed. See "Fixes landed" below. Re-validation in flight.

## TL;DR

Phase 1 (#68) E2E validation of the **synthetic baseline path** surfaced **two latent bugs** that had been masked by the live deploy always running `from_source` (real HUPA-UCM data). Both are now fixed locally on branch `feature/dual-baseline-mmt-aws-usw2`. Pre-merge-to-main retest in flight.

| Bug | Where | Why latent | Fix |
|---|---|---|---|
| 1. `SCHEMA_NOT_FOUND` in `validate_baseline_source` | First task of `glucosphere_full_setup` | Live target's `glucosphere_dev` schema pre-existed from prior deploys; fresh sandbox schemas don't | Added `CREATE SCHEMA IF NOT EXISTS` before `CREATE TABLE baseline_provenance` (commit `398d637`) |
| 2. Stratified-sampler plan-size assertion fails | `dual_04_*` line 109 | Synthetic phenotypes produced 0 patients in `hypo_prone` + `mixed` strata; real HUPA-UCM naturally covers all 4 | Added 2 phenotypes: hypo-prone (mean 75, std 20) + brittle T1D (mean 135, std 55) to `dual_01_generate_synthetic_baseline.py` (commit `21baa5e`) |

## Context

`#68` is the Phase 1 task in our [2026-05-20 re-locked workflow sequence](#) — validate the synthetic baseline path E2E before merging the dual-baseline cleanup branch to `main`. The synthetic path hadn't been re-validated since 2026-05-15 (24+ commits ago including notebook rename, v9 palette, bidirectional cohort split).

**Setup:** committed two permanent sandbox harness targets to `databricks.yml` (`mmt_aws_usw2_synth_e2e` + `mmt_aws_usw2_from_table_e2e`) using DABs `mode: development`. These auto-prefix resources with `[dev USERNAME]` and isolate from the live `mmt_aws_usw2` target. See `databricks.yml` lines 92-149 for the canonical example.

**Verified along the way (empirical findings worth knowing for any future harness target):**

- `mode: development` auto-prefix applies to **jobs + pipelines only** — NOT to `apps:` or `database_instances:` (DNS-compliance constraints). For those, per-target `resources:` name overrides are needed.
- `${workspace.current_user.short_name}` normalizes dots to underscores in the actual deployed prefix. `may.merkletan` → `[dev may_merkletan]`.
- Databricks App names have a 30-character limit (verified empirically).

## Bug 1: SCHEMA_NOT_FOUND in `validate_baseline_source`

### Symptom

Run `598606749042992` (first synth_e2e deploy) failed immediately at the `validate_baseline_source` task:

```
[SCHEMA_NOT_FOUND] The schema `mmt_aws_usw2_catalog.glucosphere_synth_e2e` cannot be found.
... CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.baseline_provenance (
        baseline_source STRING, source_detail STRING, last_run_at TIMESTAMP)
```

### Root cause

`validate_baseline_source` is the FIRST task in `glucosphere_full_setup` and tries to write a `baseline_provenance` table to the deploy-target's `{catalog}.{schema}`. The schema creation lives in `dual_01_generate_synthetic_baseline.py:18` and `dual_01_ingest_real_baseline.py:75` — but those run AFTER the dispatch task, which runs AFTER validate. So for any **fresh** schema (new workspace, new sandbox target), validate fires before any code has created the schema.

For the live `mmt_aws_usw2` target, `glucosphere_dev` was created on the first deploy back in 2026-05-15 and has persisted ever since. The bug never surfaced there.

### Fix

`Data_DataGen_ModelForecast/utils/dual_validate_baseline_source.py:107` (commit `398d637`):

```python
# Ensure schema exists before writing provenance. dual_01_* notebooks (which
# create the schema themselves) run AFTER this validate task, so for any fresh
# sandbox deploy ... the schema doesn't exist yet at this point. Idempotent
# CREATE SCHEMA IF NOT EXISTS — no-op for existing schemas.
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}")
```

The redundant `CREATE SCHEMA` calls in `dual_01_*.py` are left intact — defensive, idempotent, no harm.

### Verified by

Retry run `891637990308752` task `validate_baseline_source`: **SUCCESS**. The fix works.

## Bug 2: Stratified-sampler plan-size assertion fails on synthetic distribution

### Symptom

Retry run `891637990308752` task `datagen_modeling` first attempt (run_id `767146243479756`):

```
AssertionError: [plan-size] expected 1000 pseudo patients in
  mmt_aws_usw2_catalog.glucosphere_synth_e2e.gen_pseudo_plan_7d, got 935.
Per-stratum targets: hypo=64, normal=717, hyper=218, mixed=1 (sum=1000).
"If a stratum was skipped (n_available == 0), the sum will fall short."
```

### Root cause

`dual_04_CGM_PseudoGeneration_CleanData_Modeling.py:422-428` classifies each source patient into one of 4 strata:

| Stratum | Threshold |
|---|---|
| hypo_prone | >15% readings <70 mg/dL |
| hyper_prone | >40% readings >180 mg/dL |
| normal_stable | >60% readings in [70, 180] |
| mixed | else (residual) |

`dual_04:504-507` then HARDCODES per-stratum sample targets to match HUPA-UCM real-distribution ratios (`hypo=64`, `normal=717`, `hyper=218`, `mixed=1` for `NUM_PSEUDO=1000`). The sampler oversamples WITH REPLACEMENT from each stratum's source patients to hit the target.

**The original 6 phenotypes in `dual_01_generate_synthetic_baseline.py`** all had mean 95-175 and std 12-45. Per AR(1) generation + `np.clip(40, 400)`:
- No phenotype produces >15% readings <70 → **hypo_prone stratum was empty**
- No phenotype produces the broad-distribution profile needed for mixed → **mixed stratum was empty**
- Sampler can't sample 64 hypo + 1 mixed from 0 source patients → assertion fires

For the live `from_source` path, real HUPA-UCM data naturally covers all 4 strata (6.59% hypo + diverse glucose dynamics across 25 patients), so the sampler succeeds.

### Fix

`Data_DataGen_ModelForecast/dual_01_generate_synthetic_baseline.py:52-69` (commit `21baa5e`):

```python
PHENOTYPES = [
    (95,  15, "Type1"),   # well-controlled T1D            → normal_stable
    (140, 30, "Type1"),   # poorly-controlled T1D          → normal_stable/borderline-hyper
    (110, 20, "Type2"),   # well-controlled T2D            → normal_stable
    (160, 40, "Type2"),   # poorly-controlled T2D          → hyper_prone
    (100, 12, "Type1"),   # tight control                  → normal_stable
    (175, 45, "Type2"),   # high baseline                  → hyper_prone
    (75,  20, "Type1"),   # NEW: hypo-prone               → hypo_prone (>15% <70)
    (135, 55, "Type1"),   # NEW: brittle/labile T1D        → mixed (high-var both ways)
]
```

With `N_PATIENTS=60` cycling through 8 phenotypes, expect 7-8 patients per phenotype. The 7-8 hypo-prone + 7-8 brittle patients should populate the previously-empty strata.

### Validation pending

Re-run synth_e2e after this fix. Read `dual_04`'s "Patient Classification Complete" stratum-counts print (lines 442-448) to verify all 4 strata are non-empty.

### Stats-drift expectation

The 2026-05-16 distribution stats captured in `ref_notes/2026-05-16_dual-baseline-comparison-plots.md` + memory `project_dual_baseline_comparison_results.md` (synthetic mean=134.9, std=34, 0.14% hypo) will shift:

- Hypoglycemia % up (was 0.14% with no hypo-prone phenotype)
- Std up (broader phenotype mix)
- Mean approximately unchanged (new phenotypes balance low + medium)

Will capture new numbers when synth_e2e completes successfully.

## Why both bugs were latent

Both bugs were specific to **fresh-schema** + **synthetic-mode** deploys. Neither condition has held since 2026-05-16 when `baseline_source` default flipped to `from_source` + `glucosphere_dev` was populated. The live deploy has been running in a perpetually-warm state that masked both issues.

Lesson: **harness-based validation against fresh state catches what production-ish testing can't.** This is exactly why the permanent sandbox harness targets (committed in `databricks.yml`) are worth keeping — they exercise the exact code paths customers / fresh-workspace deploys would hit.

## Related context for team

- **Phase 1 #68 finishes when**: synth_e2e validates SUCCESS + from_table_e2e validates SUCCESS. Then phase 2 cleanup → phase 3 merge to main can proceed.
- **Memory of the rename pass**: `real_from_source` → `from_source` and `real_from_table` → `from_table` (mode names now describe mechanism, not data origin). Source-agnostic — `from_table` works on synthetic-populated source too. See CHANGELOG.md 2026-05-26 entry.
- **`from_table_e2e` source is self-bootstrapping**: pulls from `glucosphere_synth_e2e.diabetes_data` (i.e., synth_e2e output). So synth_e2e must succeed before from_table_e2e can run.

## How to retry the validation

```bash
# Synth E2E
databricks bundle deploy -t mmt_aws_usw2_synth_e2e --profile fevm-mmt-aws-usw2
databricks bundle run glucosphere_full_setup -t mmt_aws_usw2_synth_e2e --profile fevm-mmt-aws-usw2 --no-wait

# Watch the stratum classification cell output in dual_04 to confirm
# all 4 strata have non-zero patient counts before the plan-size assertion fires.

# After SUCCESS — from_table E2E (sources from synth output)
databricks bundle deploy -t mmt_aws_usw2_from_table_e2e --profile fevm-mmt-aws-usw2
databricks bundle run glucosphere_full_setup -t mmt_aws_usw2_from_table_e2e --profile fevm-mmt-aws-usw2 --no-wait

# Cleanup both harnesses after validation (bundle destroy doesn't auto-drop UC schemas)
databricks bundle destroy -t mmt_aws_usw2_synth_e2e --auto-approve --profile fevm-mmt-aws-usw2
databricks bundle destroy -t mmt_aws_usw2_from_table_e2e --auto-approve --profile fevm-mmt-aws-usw2
# Then manually DROP SCHEMA glucosphere_synth_e2e + glucosphere_from_table_e2e CASCADE
```

## Open question for team

`dual_04`'s target ratios are HARDCODED to HUPA-UCM proportions. Should they adapt to the source distribution dynamically (would make the sampler robust to any future cohort shift), or should we treat the hardcoded ratios as a contract that source data must satisfy (current state, with this fix the contract is now satisfied for synthetic too)? Either's defensible — flagging because someone may want to revisit.

For now: phenotype change is the minimal fix that ships #68. Sampler adaptivity = follow-up if surfaced as friction later.
