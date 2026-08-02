export { ACCENT } from './theme.js';

export const RED = '#ef4444';
export const AMBER = '#f59e0b';
export const GREEN = '#22c55e';
export const MUTED = 'var(--fg3,#71717a)';

export function envStyle(env) {
  return env === 'production'
    ? { envColor: '#fca5a5', envBg: 'rgba(239,68,68,0.12)' }
    : { envColor: '#fcd34d', envBg: 'rgba(245,158,11,0.12)' };
}

// Build sparkline bar data from a raw array
// color: base color, lastColor: override for last bar (for stat cards)
export function mkBars(data, color, lastColor) {
  const max = Math.max(...data, 1);
  return data.map((v, i) => ({
    h: Math.round(100 * v / max),
    color: (lastColor && i === data.length - 1) ? lastColor : color,
  }));
}

// Build sparkline bars for issue trend rows
export function mkSpark(data, color) {
  const max = Math.max(...data, 1);
  return data.map(v => ({ h: Math.round(100 * v / max), color }));
}

export function dotColor(status, spiking) {
  if (status === 'resolved') return 'var(--fg5,#3f3f46)';
  if (spiking) return RED;
  if (status === 'regressed') return AMBER;
  return ACCENT;
}

export function tagProps(status, spiking) {
  if (spiking && status !== 'resolved') return { tag: 'spiking', tagColor: '#fca5a5', tagBg: 'rgba(239,68,68,0.12)' };
  if (status === 'regressed') return { tag: 'regression', tagColor: '#fcd34d', tagBg: 'rgba(245,158,11,0.12)' };
  if (status === 'resolved') return { tag: 'resolved', tagColor: 'var(--fg2,#a1a1aa)', tagBg: 'var(--border2,#27272a)' };
  return { tag: '', tagColor: '', tagBg: '' };
}

export const MONO = "'Geist Mono',monospace";
export const SANS = "'Geist',system-ui,sans-serif";

// Pill style for severity tags on alert rows
export function sevStyle(sev) {
  if (sev === 'spike' || sev === 'threshold') return { color: '#fca5a5', bg: 'rgba(239,68,68,0.12)' };
  if (sev === 'regression' || sev === 'deploy') return { color: '#86efac', bg: 'rgba(34,197,94,0.12)' };
  if (sev === 'llm') return { color: '#c4b5fd', bg: 'rgba(167,139,250,0.12)' };
  return { color: 'var(--fg2,#a1a1aa)', bg: 'var(--border2,#27272a)' };
}

export function sevDot(sev) {
  if (sev === 'spike' || sev === 'threshold') return RED;
  if (sev === 'regression') return AMBER;
  if (sev === 'deploy') return GREEN;
  if (sev === 'llm') return '#a78bfa';
  return MUTED;
}
