#!/usr/bin/env bash
# deploy_sandbox.sh — ONE command to stand up your own isolated Glucosphere
# "sandbox": its own data + its own Genie/Knowledge-Assistant/Supervisor + its
# own app, so you can build features without touching the live demo.
#
# WHO THIS IS FOR: contributors who want a private copy to develop against.
#
# SETUP (once): copy .env.bundle.example -> .env.bundle and fill 4 lines —
#   BUNDLE_VAR_catalog        which catalog the data goes in
#   BUNDLE_VAR_schema         the "folder" name for the data
#   DATABRICKS_CONFIG_PROFILE which workspace login to use
#   BUNDLE_VAR_dev_initials   YOUR initials (keeps your copy separate)
#
# USAGE:
#   ./scripts/deploy_sandbox.sh                      # real data (HUPA-UCM), suffix = _<your initials>
#   ./scripts/deploy_sandbox.sh synth_e2e            # synthetic data instead of real
#   ./scripts/deploy_sandbox.sh from_source_e2e _v2  # custom agent suffix (advanced)
#   ./scripts/deploy_sandbox.sh --help
#
# It prints a plan and asks "Proceed? [y/N]" before doing anything. The full
# run takes ~50 min and creates BILLED Agent Bricks endpoints. The live
# `gsphere` deploy (production app + agents) is never touched.
set -euo pipefail

case "${1:-}" in
  -h|--help) awk 'NR==1{next} /^#/{sub(/^# ?/,"");print;next} {exit}' "$0"; exit 0 ;;
esac

# Arg 1: which data mode (maps to a DABs harness target). Arg 2 (optional):
# explicit agent suffix; defaults to _<dev_initials> so it's automatic + unique.
HARNESS_TYPE="${1:-from_source_e2e}"
SUFFIX_ARG="${2:-}"

case "$HARNESS_TYPE" in
  synth_e2e|from_table_e2e|from_source_e2e) ;;
  *) echo "ERROR: data mode must be one of: synth_e2e | from_table_e2e | from_source_e2e (got '$HARNESS_TYPE')"; exit 1 ;;
esac

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
[ -f .env.bundle ] || { echo "ERROR: .env.bundle not found in $REPO_ROOT. Copy .env.bundle.example -> .env.bundle and fill in the 4 fields."; exit 1; }

# Load operator config + the harness schema/baseline for this data mode.
# (.env.bundle's HARNESS_TYPE block appends the schema suffix + sets baseline.)
# shellcheck disable=SC1091
HARNESS_TYPE="$HARNESS_TYPE" source .env.bundle

# Agent/endpoint name suffix: default to _<dev_initials> so each contributor's
# agents are auto-named and don't collide. Override with arg 2 if you must.
SUFFIX="${SUFFIX_ARG:-_${BUNDLE_VAR_dev_initials:-user}}"
export BUNDLE_VAR_harness_suffix="$SUFFIX"
TARGET="gsphere_${HARNESS_TYPE}"

# Fail early + clearly on missing required config (idiot-proof).
: "${BUNDLE_VAR_catalog:?set BUNDLE_VAR_catalog in .env.bundle}"
: "${BUNDLE_VAR_schema:?set BUNDLE_VAR_schema in .env.bundle}"
PROFILE="${DATABRICKS_CONFIG_PROFILE:?set DATABRICKS_CONFIG_PROFILE in .env.bundle}"

# Resolve the app name from the bundle (handles the source-e2e vs from_source
# naming quirk without hardcoding).
APP_NAME="$(databricks bundle validate -t "$TARGET" -o json 2>/dev/null \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print(next(iter(d.get('resources',{}).get('apps',{}).values()),{}).get('name',''))")"
[ -n "$APP_NAME" ] || { echo "ERROR: could not resolve the app name for target '$TARGET'. Is the databricks CLI authenticated for profile '$PROFILE'?"; exit 1; }

cat <<EOF

  +-- Glucosphere sandbox deploy -------------------------------
  | data mode : $HARNESS_TYPE
  | target    : $TARGET
  | catalog   : $BUNDLE_VAR_catalog
  | schema    : $BUNDLE_VAR_schema
  | baseline  : ${BUNDLE_VAR_baseline_source:-(target default)}
  | agents    : Glucosphere_{KA,Supervisor,Intelligence}${SUFFIX}
  | app       : $APP_NAME
  | profile   : $PROFILE
  +------------------------------------------------------------
  Runs the full ~50-min setup (data + agents + app) and creates BILLED
  Agent Bricks endpoints. The live 'gsphere' production deploy is NOT touched.

EOF
read -rp "  Proceed? [y/N] " ans
[ "$ans" = "y" ] || { echo "Aborted — nothing deployed."; exit 1; }

step() { echo; echo ">>> $*"; "$@"; }

# 1-2. Deploy (pass 1 creates the warehouse) -> render app.yaml -> deploy (pass 2).
step databricks bundle deploy -t "$TARGET"
step uv run python scripts/render_app_yaml.py --target "$TARGET"
step databricks bundle deploy -t "$TARGET"

# 3. Build the data + create THIS sandbox's Genie/KA/MAS + forecast endpoints.
step databricks bundle run glucosphere_full_setup -t "$TARGET"

# 4. Wire the freshly-created agents into the app (auto-discovered by name) + redeploy.
step uv run python scripts/render_app_yaml.py --target "$TARGET" --discover-agents
step databricks bundle deploy -t "$TARGET"

# 5. Grant the app's service principal access to data + warehouse + agents.
step uv run python scripts/grant_app_sp.py --app "$APP_NAME" --profile "$PROFILE"

cat <<EOF

  ✅ Sandbox ready.
     app     : $APP_NAME   (URL: databricks apps get "$APP_NAME" -p "$PROFILE")
     data    : $BUNDLE_VAR_catalog.$BUNDLE_VAR_schema
     agents  : Glucosphere_*${SUFFIX}

  Note: render rewrote App/databricks/app.yaml to point at your sandbox. The
  deployed app already has it; to restore the committed (live) version locally:
     git checkout -- App/databricks/app.yaml
EOF
