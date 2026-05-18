// Runtime app config fetched from Flask backend.
//
// Flask /api/config (in App/databricks/app.py) reads CATALOG_NAME + SCHEMA_NAME
// + GENIE_SPACE_ID from environment (set per-target in App/databricks/app.yaml)
// and exposes them here. All SQL queries in the React app MUST use these values
// via template literals — NEVER hardcode catalog/schema names.
//
// Usage:
//   import { getConfig, withConfig } from '../../api/config';
//   const { catalog, schema } = await getConfig();
//   const query = `SELECT * FROM ${catalog}.${schema}.gold_patient_device_readings`;
//
// The config is fetched once at app startup and cached. Subsequent calls return
// the cached promise (so concurrent callers share one network round-trip).

let _configPromise = null;

export function getConfig() {
  if (_configPromise) return _configPromise;
  _configPromise = fetch('/api/config')
    .then(r => {
      if (!r.ok) {
        throw new Error(`Failed to fetch /api/config: ${r.status} ${r.statusText}`);
      }
      return r.json();
    })
    .then(cfg => {
      if (!cfg.catalog || !cfg.schema) {
        console.error('[config] /api/config returned missing fields:', cfg);
        throw new Error('App config missing catalog/schema — check app.yaml env vars');
      }
      console.log('[config] loaded:', cfg);
      return cfg;
    })
    .catch(err => {
      // Clear cache so a subsequent call can retry
      _configPromise = null;
      throw err;
    });
  return _configPromise;
}

/**
 * Helper for query functions: wraps an async function that needs catalog/schema.
 *
 *   export async function getDeviceCount() {
 *     return withConfig(async ({ catalog, schema }) => {
 *       const query = `SELECT COUNT(*) FROM ${catalog}.${schema}.silver_patient_registry`;
 *       return executeSQLQuery(query);
 *     });
 *   }
 */
export async function withConfig(fn) {
  const cfg = await getConfig();
  return fn(cfg);
}
