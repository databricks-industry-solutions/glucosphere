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

## Known issue: marketplace catalog version mismatch

The `fe-vibe` marketplace entry for `databricks-ai-dev-kit` advertises `version: "1.0.0"` but the actual repo's latest tag is `v0.1.11` at time of writing. The install still succeeds because the marketplace's `source.ref` points to `main`. If a future install fails with a version/tag error, check the entry in `~/.vibe/marketplace/.claude-plugin/marketplace.json` and report to the fe-vibe maintainers.
