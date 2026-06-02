import { useNavigate, useLocation } from 'react-router-dom';

// Shared back-arrow handler. Returns to the previous page (browser back) when
// there is in-app history, else falls back to `fallback` (home by default) —
// e.g. when the page was opened cold via a deep link or a fresh tab.
//
// react-router-dom marks the very first/entry location with key 'default';
// after any in-app navigation the key is a unique id. So key === 'default'
// means "no prior in-app history → don't call navigate(-1) (it would leave
// the app or no-op), use the fallback instead."
export function useGoBack(fallback = '/') {
  const navigate = useNavigate();
  const location = useLocation();
  return () => (location.key === 'default' ? navigate(fallback) : navigate(-1));
}
