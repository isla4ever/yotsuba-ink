import { useEffect, useState } from 'react';

const desktopQuery = '(min-width: 1024px)';
const wideQuery = '(min-width: 1280px)';

function queryMatches(query: string) {
  return typeof window !== 'undefined' && window.matchMedia(query).matches;
}

export function useSidebarViewport() {
  const [desktop, setDesktop] = useState(() => queryMatches(desktopQuery));
  const [wide, setWide] = useState(() => queryMatches(wideQuery));

  useEffect(() => {
    const desktopMedia = window.matchMedia(desktopQuery);
    const wideMedia = window.matchMedia(wideQuery);
    const update = () => {
      setDesktop(desktopMedia.matches);
      setWide(wideMedia.matches);
    };
    update();
    desktopMedia.addEventListener('change', update);
    wideMedia.addEventListener('change', update);
    return () => {
      desktopMedia.removeEventListener('change', update);
      wideMedia.removeEventListener('change', update);
    };
  }, []);

  return { desktop, wide };
}
