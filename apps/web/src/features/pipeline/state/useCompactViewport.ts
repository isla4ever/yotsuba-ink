import { useEffect, useState } from 'react';

const compactViewportQuery = '(max-width: 760px)';

export function useCompactViewport() {
  const [compact, setCompact] = useState(() => (
    typeof window !== 'undefined' && window.matchMedia(compactViewportQuery).matches
  ));

  useEffect(() => {
    const query = window.matchMedia(compactViewportQuery);
    const update = () => setCompact(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);

  return compact;
}
