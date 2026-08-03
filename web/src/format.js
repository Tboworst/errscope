// Relative time: "just now", "3m ago", "2h ago", "6d ago"
export function relativeTime(isoStr) {
  if (!isoStr) return '';
  const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  return Math.floor(diff / 86400) + 'd ago';
}

// Short date: "Jul 30, 09:12"
export function shortDate(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  const month = d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
  const day = d.getUTCDate();
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const mm = String(d.getUTCMinutes()).padStart(2, '0');
  return `${month} ${day}, ${hh}:${mm}`;
}

// Token formatting: 2.8M / 512k
export function fmtTokens(n) {
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return Math.round(n / 1e3) + 'k';
  return String(n);
}

// Cost: $x.xxxx
export function fmtCost(n) {
  return '$' + (n || 0).toFixed(4);
}

// Count with locale separators
export function fmtCount(n) {
  return (n || 0).toLocaleString();
}
