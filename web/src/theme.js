export const ACCENT = '#6366f1';
export const DENSITY = 'comfortable';
export const ROW_PAD = '11px'; // comfortable

const THEMES = {
  zinc: {}, // CSS defaults (zinc is the default; no overrides needed)
  slate: {
    bg: '#0a0f16', sheet: '#0c121b', panel: '#101826', code: '#111a29',
    hover: '#152030', border: '#1b2839', divider: '#141f2d', border2: '#233349',
    fg: '#f1f5f9', fg0: '#e2e8f0', fg1: '#cbd5e1', fg2: '#94a3b8',
    fg3: '#64748b', fg4: '#475569', fg5: '#334155',
  },
  warm: {
    bg: '#0c0a09', sheet: '#0e0c0b', panel: '#131110', code: '#141211',
    hover: '#1c1917', border: '#221f1d', divider: '#191614', border2: '#2b2725',
    fg: '#fafaf9', fg0: '#e7e5e4', fg1: '#d6d3d1', fg2: '#a8a29e',
    fg3: '#78716c', fg4: '#57534e', fg5: '#44403c',
  },
  forest: {
    bg: '#070b09', sheet: '#090e0c', panel: '#0d1411', code: '#0e1512',
    hover: '#131c17', border: '#18231d', divider: '#111a15', border2: '#203128',
    fg: '#ecf5ef', fg0: '#dce8e0', fg1: '#cddbd2', fg2: '#9ab0a3',
    fg3: '#6b8274', fg4: '#4c5f54', fg5: '#39473f',
  },
};

const CSS_VARS = ['bg','sheet','panel','code','hover','border','divider','border2','fg','fg0','fg1','fg2','fg3','fg4','fg5'];

export function applyTheme(name) {
  const t = THEMES[name] || {};
  CSS_VARS.forEach(k => {
    if (t[k]) document.documentElement.style.setProperty('--' + k, t[k]);
    else document.documentElement.style.removeProperty('--' + k);
  });
}
