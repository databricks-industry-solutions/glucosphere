# Internal Setup — Databricks Employees Only

This guide covers Claude Code plugin setup using the Databricks Field Engineering internal `fe-vibe` plugin marketplace. **It only works inside the Databricks corp network.** External contributors should refer to the public-plugin section in the main [`README.md`](../README.md) instead.

These plugins are entirely optional — **none are required to deploy or run Glucosphere**. They multiply leverage when authoring, extending, or debugging the codebase from inside Claude Code (Anthropic CLI).

---

## Prerequisite: git HTTPS rewrite for github.com (one-time)

The Databricks `fe-vibe` plugin marketplace installs plugins via `git clone` from GitHub. By default Claude Code attempts SSH (`git@github.com:`), which fails with `Permission denied (publickey)` if no SSH key is registered. Public repos work fine over HTTPS — make git auto-rewrite SSH → HTTPS:

```bash
git config --global url."https://github.com/".insteadOf "git@github.com:"
```

Verify:
```bash
git config --get-all url.https://github.com/.insteadof
# Expected output: git@github.com:

# Confirm git now resolves SSH URLs via HTTPS:
git ls-remote git@github.com:databricks-solutions/ai-dev-kit.git 2>&1 | head -2
# Should return tag refs (rewritten to HTTPS internally) — not "Permission denied"
```

---

## How to install (TUI is most reliable)

Open the plugin TUI and use the Discover tab — easier than typing CLI commands one at a time:

```
/plugin                       # opens the TUI
# In TUI: Discover → search by name → select → install
```

If you prefer CLI, the subcommand is `install` (not `add`):

```text
/plugin install <plugin-name>@<marketplace>
```

After each install, Claude Code prompts you to run `/reload-plugins` to apply.

---

## Recommended Databricks-relevant plugins for glucosphere maintainers ("Persona B")

| Plugin | Marketplace | Why |
|---|---|---|
| `databricks-ai-dev-kit` | fe-vibe | Core: 25+ skills incl. Lakebase, Apps, bundles, jobs, Genie, MAS, SDK |
| `apx` | fe-vibe | React + FastAPI Databricks Apps patterns |
| `fe-app-toolkit` | fe-vibe | Reusable App building blocks (React template + Lakebase semantic cache) |
| `fe-lovable-databricks` | fe-vibe | Lakebase connection patterns + migration playbook |
| `convert-postgres-app-to-lakebase` | experimental | Postgres → Lakebase end-to-end conversion |
| `fe-hls` | fe-vibe | HLS / PHI compliance (HIPAA Safe Harbor) checker |
| `fe-databricks-tools` | fe-vibe | General Databricks workflow tools (auth, queries, deployments) |
| `databricks-architect` | fe-vibe | Architecture decision frameworks |
| `dbapps` | experimental | Apps security review |
| `feature-status` | experimental | Check Databricks feature GA / Public Preview / Gated status |

---

## Useful general dev plugins (broader than glucosphere)

If you do other Databricks projects or general AI-assisted dev, these are high-leverage adds:

| Plugin | Why |
|---|---|
| `code-review` | PR code review automation |
| `pr-review-toolkit` | Deeper PR review patterns |
| `commit-commands` | `/commit` and `/commit-push-pr` shortcuts |
| `feature-dev` | Feature development scaffolding |
| `claude-md-management` | CLAUDE.md improver — useful for keeping project context current |
| `skill-creator` | Create your own Claude Code skills |
| `github` | GitHub integration |
| `security-guidance` | Security review patterns |
| `playwright` | Browser automation for end-to-end testing |
| `claude-notify` | macOS desktop notifications for Claude completion events |
| `claude-code-setup` | Claude automation recommender |

---

## Minimal set — deploy/demo only ("Persona A")

If you're just running the demo (not extending the code):

```text
/plugin install databricks-ai-dev-kit@fe-vibe
/plugin install one-shot-demo@fe-vibe
```

---

## Verify plugins installed

```bash
ls ~/.claude/plugins/cache/fe-vibe/ 2>/dev/null
# Should list installed plugin directories

cat ~/.claude/plugins/installed_plugins.json | python3 -m json.tool | grep -E "databricks|fe-|apx"
# Should show install entries with paths + versions
```

---

## Persistence

Plugins install into `~/.claude/plugins/` and persist across sessions, re-logins, and Claude Code updates. They're only removed via explicit `/plugin remove`, manual cleanup, or machine wipe. **One-time setup per machine.**

---

## Catalog naming convention (internal fevm workspaces)

> The workspace/catalog names below are **intentionally documented** — they're non-secret
> internal conveniences (profile aliases + catalog names; no hosts, ids, or credentials),
> and this doc's purpose is to point internal maintainers at the shared coords. For access
> to the shared workspace/catalogs, **reach out to the Glucosphere maintainers**; then save
> your coords into your own gitignored `.env.bundle.<target>` (copied from
> [`.env.bundle.example`](../.env.bundle.example)) — never into committed files.

Internal Databricks workspaces (`fevm-*`) typically expose two catalog
variants for the same workspace. Treat them differently:

| Catalog form | Example (fevm-mmt-aws-usw2) | Treat as | Why |
|---|---|---|---|
| **`<workspace>_catalog`** (with `_catalog` suffix) | `mmt_aws_usw2_catalog` | **dev / staging** | Workspace-default catalog — tied to the specific fevm workspace. Use for harness e2e validation, exploratory deploys, throwaway runs. The harness targets (`*_synth_e2e`, `*_from_source_e2e`, `*_from_table_e2e`) write here when `BUNDLE_VAR_catalog` points at this catalog in their `.env.bundle.<target>` file — they differ from the live target by their isolated `_*_e2e` schema (set in the per-target file), not by catalog. |
| **`<workspace>`** (no `_catalog` suffix, standalone) | `mmt_aws_usw2` | **production / live demo** | Standalone catalog — created independently of the workspace, portable across workspaces if needed. Use for the canonical live demo deploy, customer-facing recordings, anything that needs to survive a workspace migration. Live target writes here per `.env.bundle.gsphere` (`BUNDLE_VAR_catalog=mmt_aws_usw2`). |

In short: **the `_catalog`-suffixed name is dev; the standalone name is
prod**. Don't conflate them when wiring up new targets or running ad-hoc
queries — the production catalog should not absorb dev/test runs and vice
versa.

### Caveat — this is a maintainer convention, not a Databricks-wide rule

This dev/prod catalog split is **set up by the current Glucosphere
maintainers** for the `mmt_aws_usw2` workspace specifically. Both catalog
variants (`mmt_aws_usw2_catalog` and `mmt_aws_usw2`) were created and
role-assigned by the dev team here — it's not a universal Databricks
or fevm-org policy.

If you're working on a different fevm workspace (or wiring up a
production-tier deploy elsewhere), **check with the workspace owner
first** before assuming the same split holds — other workspaces may
not have a standalone catalog provisioned, may use a different naming
scheme, or may reserve catalog creation behind admin approval.

External contributors using their own (non-fevm) workspace don't have this
two-catalog convention — they just use whichever catalog name they create.
The widget defaults (`your_workspace_catalog`) reflect the external-user
case; internal contributors override via their `.env.bundle.<target>` files.

---

## Known issue: marketplace catalog version mismatch

The `fe-vibe` marketplace entry for `databricks-ai-dev-kit` advertises `version: "1.0.0"` but the actual repo's latest tag is `v0.1.11` at time of writing. The install still succeeds because the marketplace's `source.ref` points to `main`. If a future install fails with a version/tag error, check the entry in `~/.vibe/marketplace/.claude-plugin/marketplace.json` and report to the fe-vibe maintainers.
