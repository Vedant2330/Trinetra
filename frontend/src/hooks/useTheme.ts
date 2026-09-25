// Theme provider — dark-first, persisted, system-aware.
//
// Applies the `.dark` class to <html> so Tailwind's `darkMode: 'class'`
// switches the whole token system in one place. No layout shift: the
// class is set before first paint via a bootstrap script in index.html
// (see inline <script>), and this hook only re-applies it when the
// operator toggles or the system preference changes.
//
// Honours `prefers-reduced-motion` is not relevant here; what IS
// relevant is `prefers-color-scheme` — never force dark on a user who
// has light set system-wide unless they explicitly chose dark.

export type Theme = 'light' | 'dark' | 'system';

const KEY = 'trinetra-theme';
const ROOT = (): HTMLElement | null =>
  typeof document !== 'undefined' ? document.documentElement : null;

function systemPrefersDark(): boolean {
  if (typeof window === 'undefined') return true; // SSR/default = dark-first
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function resolvedOf(t: Theme): boolean {
  if (t === 'dark') return true;
  if (t === 'light') return false;
  return systemPrefersDark();
}

function apply(dark: boolean) {
  const r = ROOT();
  if (!r) return;
  r.classList.toggle('dark', dark);
  // Reflect on the body too so any element-scoped styles resolve
  document.body.classList.toggle('dark', dark);
}

/** Read the persisted/system theme and apply it immediately. */
export function initTheme(): Theme {
  let stored: Theme | null = null;
  try { stored = localStorage.getItem(KEY) as Theme | null; } catch { /* ignore */ }
  const theme: Theme = stored && ['light', 'dark', 'system'].includes(stored) ? stored : 'system';
  apply(resolvedOf(theme));
  return theme;
}

export function useTheme() {
  // Lazy — the hook is only meaningful in the browser. The bootstrap
  // script in index.html handles first paint; this hook handles changes.
  if (typeof window === 'undefined') {
    return { theme: 'system' as const, setTheme: () => {}, resolved: true };
  }

  // Re-read on every render is cheap; we keep state in App.tsx and pass
  // setTheme down. This module is the single source of truth for the
  // class↔token mapping so no component hardcodes a theme.
  return {
    theme: (localStorage.getItem(KEY) as Theme) ?? 'system',
    setTheme: (t: Theme) => {
      try { localStorage.setItem(KEY, t); } catch { /* ignore */ }
      apply(resolvedOf(t));
      // Let the OS-level media query listener know it may need re-eval
      window.dispatchEvent(new Event('trinetra-theme'));
    },
    resolved: resolvedOf((localStorage.getItem(KEY) as Theme) ?? 'system'),
  };
}

/** Re-apply the resolved theme when the OS preference changes. */
export function useSystemThemeEffect() {
  if (typeof window === 'undefined') return;
  const mq = window.matchMedia('(prefers-color-scheme: dark)');
  const onMatch = () => {
    const stored = localStorage.getItem(KEY);
    if (!stored || stored === 'system') apply(systemPrefersDark());
  };
  mq.addEventListener('change', onMatch);
  return () => mq.removeEventListener('change', onMatch);
}