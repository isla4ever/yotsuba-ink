import { useEffect, useState } from 'react';
import {
  defaultSidebarExpanded,
  hasSidebarPreference,
  loadSidebarExpanded,
  saveSidebarExpanded,
} from './workbenchSidebarModel';

// Lifted out of WorkbenchSidebar so the command palette can toggle the same preference.
export function useSidebarPreference(wide: boolean) {
  const [expanded, setExpanded] = useState(() => loadSidebarExpanded(defaultSidebarExpanded(wide)));

  useEffect(() => {
    if (hasSidebarPreference()) return;
    setExpanded(defaultSidebarExpanded(wide));
  }, [wide]);

  const toggle = () => {
    setExpanded((current) => {
      const next = !current;
      saveSidebarExpanded(next);
      return next;
    });
  };

  return { expanded, toggle };
}
