import { useEffect, useState } from 'react';

type ThemeMode = 'dark' | 'light';

export function useThemeMode() {
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const stored = localStorage.getItem('novel-workflow-theme');
    if (stored === 'dark' || stored === 'light') return stored;
    return 'dark';
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('novel-workflow-theme', theme);
  }, [theme]);

  return { theme, setTheme };
}
