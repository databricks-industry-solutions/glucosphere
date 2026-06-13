# Dependencies — App (license inventory)

Canonical dependency + license inventory for the App's frontend (`package.json`),
backend (`App/databricks/requirements.txt`), and the platform services it consumes at
runtime. Kept as a dedicated file so license audits have one stable per-area location;
see also [`Data_DataGen_ModelForecast/DEPENDENCIES.md`](../Data_DataGen_ModelForecast/DEPENDENCIES.md).

## Frontend (`package.json`)

| Dependency | Where used | Why it's used | License |
| --- | --- | --- | --- |
| [**react**](https://github.com/facebook/react) | `App/src/*.jsx` | UI framework | MIT |
| [**react-dom**](https://github.com/facebook/react) | `App/src/main.jsx` | React renderer for browser DOM | MIT |
| [**react-router-dom**](https://github.com/remix-run/react-router) | `App/src/App.jsx`, `App/src/pages/*` | Client-side routing | MIT |
| [**lucide-react**](https://github.com/lucide-icons/lucide) | Icons across pages | Icon set | ISC |
| [**react-markdown**](https://github.com/remarkjs/react-markdown) | MetricsExplained + MAS reply rendering | Markdown → React component | MIT |
| [**vite**](https://github.com/vitejs/vite) | Build tool (`npm run build`) | Frontend bundler | MIT |
| [**@vitejs/plugin-react**](https://github.com/vitejs/vite-plugin-react) | `vite.config.js` | React fast-refresh + JSX support | MIT |
| [**tailwindcss**](https://github.com/tailwindlabs/tailwindcss) | `tailwind.config.js` + all components | Utility-first CSS | MIT |
| [**postcss**](https://github.com/postcss/postcss) | `postcss.config.js` | CSS transform pipeline (Tailwind processor) | MIT |
| [**autoprefixer**](https://github.com/postcss/autoprefixer) | `postcss.config.js` | Vendor-prefix automation | MIT |
| [**@types/react**](https://github.com/DefinitelyTyped/DefinitelyTyped) | dev-time type hints | TypeScript type definitions (dev-only) | MIT |
| [**@types/react-dom**](https://github.com/DefinitelyTyped/DefinitelyTyped) | dev-time type hints | TypeScript type definitions (dev-only) | MIT |

## Backend (`App/databricks/requirements.txt`)

| Dependency | Where used | Why it's used | License |
| --- | --- | --- | --- |
| [**flask**](https://github.com/pallets/flask) | `App/databricks/app.py` | HTTP server framework (routes for `/api/sql/query`, `/api/config`, `/api/assist`, `/api/genie/query`, `/api/alerts*`, `/uc-assets/`) | BSD-3-Clause |
| [**requests**](https://github.com/psf/requests) | `App/databricks/app.py` | Outbound HTTP to Databricks Statement Execution API, KA/MAS serving endpoints, UC Files API | Apache-2.0 |
| [**psycopg[binary]**](https://github.com/psycopg/psycopg) | `App/databricks/lakebase.py` (lazily imported; exercised only on Lakebase-configured targets) | PostgreSQL driver for the Lakebase alert-triage OLTP store | **LGPL-3.0** |

**Note on package URLs.** GitHub source repos linked on names above. If your Databricks workspace or corporate network blocks direct PyPI / npm egress, see the [note on package URLs and network reachability](../Data_DataGen_ModelForecast/DEPENDENCIES.md#note-on-package-urls-and-network-reachability) in the Data_DataGen dependency inventory for context and Databricks egress-policy pointers.

Python runtime is provided by the Databricks Apps platform — no local Python pin in `App/`. (Repo-root `scripts/` use Python 3.11 via `uv`; see [`DEPLOY.md`](../DEPLOY.md).)

## Platform services (consumed at runtime, not bundled deps)

| Service | Where used | Why it's used |
| --- | --- | --- |
| **Databricks Statement Execution API** | `App/databricks/app.py` `/api/sql/query` | Routes SQL queries to the bundle-managed serverless warehouse |
| **Foundation model** (`databricks-claude-sonnet-4-6`) | `app.py` `/api/assist` (engine=direct) | Device reasoning / Device Analysis — the default fast router's reasoning path |
| **Knowledge Assistant (KA) serving endpoint** | `app.py` `/api/assist` (called directly by the router for clinical Qs; or via MAS) | RAG over WHO clinical-guidelines PDF |
| **Genie space** | `app.py` `/api/genie/query` (CGM-data mode, direct) and via the router/MAS | NL-to-SQL over gold device tables |
| **Multi-Agent Supervisor (MAS) serving endpoint** | `app.py` `/api/assist` (engine=mas toggle) | Orchestrates Genie + KA (kept for A/B; not the default) |
| **Lakebase Autoscaling Postgres** | `App/databricks/lakebase.py` (`POST /api/2.0/postgres/credentials` for short-lived passwords + native wire protocol via psycopg) | Alert-triage OLTP store (`triage.alerts` / `triage.alert_audit`) — present only on Lakebase-enabled targets |
| **Databricks Apps Platform** | Deployment target | Hosts Flask + React static build |
