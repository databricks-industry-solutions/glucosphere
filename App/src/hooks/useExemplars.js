import { useEffect, useState } from 'react';
import { getConfig } from '../api/config';

// The Coach's false-low demo exemplar, discovered server-side from the actual
// incident data (/api/config → exemplars.false_low) so the per-patient tour step
// and the search placeholder are correct on ANY dataset (prod / sandbox / DAIS)
// rather than a hardcoded patient id that only holds while the data-gen seed is
// unchanged. null until config resolves / on error → callers fall back to a
// concrete default so copy still reads well.
//   shape: { patient_id, displayed, true_val } | null
export function useFalseLowExemplar() {
  const [exemplar, setExemplar] = useState(null);
  useEffect(() => {
    let alive = true;
    getConfig()
      .then(cfg => { if (alive) setExemplar(cfg?.exemplars?.false_low || null); })
      .catch(() => { if (alive) setExemplar(null); });
    return () => { alive = false; };
  }, []);
  return exemplar;
}
