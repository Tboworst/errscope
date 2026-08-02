import React from 'react';
import { ACCENT, RED, AMBER, sevDot } from '../styles.js';
import { relativeTime } from '../format.js';

export default function Header({
  page, q, onSearch, envFilter, onEnvFilter,
  showResolved, onToggleResolved,
  alerts, issues,
  onNavigate,
}) {
  const [searchFocus, setSearchFocus] = React.useState(false);
  const [bellOpen, setBellOpen] = React.useState(false);
  const blurTimerRef = React.useRef(null);

  const pageTitle = { issues: 'Issues', llm: 'LLM Calls', alerts: 'Alerts', deploys: 'Deploys' }[page] || 'Issues';

  const ql = q.toLowerCase();
  const searchOpen = searchFocus && ql.length > 0;

  // Bell dropdown
  React.useEffect(() => {
    if (!bellOpen) return;
    const handler = () => setBellOpen(false);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [bellOpen]);

  const bellItems = (alerts || []).slice(0, 4);
  const bellCount = Math.min((alerts || []).length, 9);

  const envButtons = [null, 'production', 'staging'].map(env => ({
    label: env ? env : 'All envs',
    bg: envFilter === env ? 'var(--border2,#27272a)' : 'transparent',
    color: envFilter === env ? 'var(--fg,#fafafa)' : 'var(--fg2,#a1a1aa)',
    weight: envFilter === env ? 600 : 400,
    onClick: () => onEnvFilter(env),
  }));

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '14px 24px', borderBottom: '1px solid var(--border,#1f1f23)', flexShrink: 0,
    }}>
      <div style={{ fontSize: 16, fontWeight: 600, letterSpacing: '-0.2px', whiteSpace: 'nowrap' }}>{pageTitle}</div>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', justifyContent: 'flex-end', rowGap: 8 }}>
        {/* Search */}
        <div style={{ position: 'relative' }}>
          <input
            value={q}
            onChange={e => onSearch(e.target.value)}
            onFocus={() => { clearTimeout(blurTimerRef.current); setSearchFocus(true); }}
            onBlur={() => { blurTimerRef.current = setTimeout(() => setSearchFocus(false), 120); }}
            placeholder="Search issues…"
            style={{
              background: 'transparent', border: '1px solid var(--border2,#27272a)',
              borderRadius: 8, color: 'var(--fg,#fafafa)', padding: '6px 12px',
              fontSize: 13, fontFamily: 'inherit', width: 'clamp(130px,16vw,220px)', outline: 'none',
            }}
          />
          {searchOpen && (
            <SearchDropdown q={q} issues={issues} onNavigate={onNavigate} />
          )}
        </div>

        {/* Env buttons */}
        <div style={{ display: 'flex', border: '1px solid var(--border2,#27272a)', borderRadius: 8, overflow: 'hidden' }}>
          {envButtons.map(b => (
            <div
              key={b.label}
              onClick={b.onClick}
              style={{ padding: '6px 12px', fontSize: 12.5, cursor: 'pointer', background: b.bg, color: b.color, fontWeight: b.weight }}
              onMouseEnter={e => { e.currentTarget.style.color = 'var(--fg,#fafafa)'; }}
              onMouseLeave={e => { e.currentTarget.style.color = b.color; }}
            >
              {b.label}
            </div>
          ))}
        </div>

        {/* Resolved toggle (issues page only) */}
        {page === 'issues' && (
          <div
            onClick={onToggleResolved}
            style={{
              padding: '6px 12px', fontSize: 12.5, cursor: 'pointer',
              border: '1px solid var(--border2,#27272a)', borderRadius: 8,
              color: showResolved ? 'var(--fg,#fafafa)' : 'var(--fg3,#71717a)',
              background: showResolved ? 'var(--border2,#27272a)' : 'transparent',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = 'var(--fg,#fafafa)'; }}
            onMouseLeave={e => { e.currentTarget.style.color = showResolved ? 'var(--fg,#fafafa)' : 'var(--fg3,#71717a)'; }}
          >
            Resolved
          </div>
        )}

        {/* Bell */}
        <div style={{ position: 'relative' }}>
          <div
            onClick={e => { e.stopPropagation(); setBellOpen(v => !v); }}
            title="Notifications"
            style={{
              position: 'relative', width: 32, height: 32,
              border: '1px solid var(--border2,#27272a)', borderRadius: 8,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', color: 'var(--fg2,#a1a1aa)', fontSize: 14,
            }}
            onMouseEnter={e => { e.currentTarget.style.color = 'var(--fg,#fafafa)'; e.currentTarget.style.background = 'var(--hover,#18181b)'; }}
            onMouseLeave={e => { e.currentTarget.style.color = 'var(--fg2,#a1a1aa)'; e.currentTarget.style.background = ''; }}
          >
            ◎
            {bellCount > 0 && (
              <span style={{
                position: 'absolute', top: -4, right: -4,
                minWidth: 15, height: 15, borderRadius: 99,
                background: '#ef4444', color: '#fff',
                fontSize: 9.5, fontWeight: 700,
                display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 3px',
              }}>
                {bellCount}
              </span>
            )}
          </div>

          {bellOpen && (
            <div
              onClick={e => e.stopPropagation()}
              style={{
                position: 'absolute', top: 38, right: 0, width: 340,
                background: 'var(--panel,#101013)',
                border: '1px solid var(--border2,#27272a)',
                borderRadius: 10, boxShadow: '0 16px 40px rgba(0,0,0,0.55)',
                zIndex: 70, overflow: 'hidden',
              }}
            >
              <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border,#1f1f23)', fontSize: 12, color: 'var(--fg3,#71717a)', fontWeight: 500 }}>
                Notifications
              </div>
              {bellItems.map((a, i) => (
                <div
                  key={i}
                  onClick={() => { setBellOpen(false); onNavigate('alerts'); }}
                  style={{
                    display: 'flex', gap: 10, padding: '10px 14px',
                    borderBottom: '1px solid var(--divider,#17171a)',
                    alignItems: 'flex-start', cursor: 'pointer',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'var(--hover,#18181b)'; }}
                  onMouseLeave={e => { e.currentTarget.style.background = ''; }}
                >
                  <span style={{ width: 7, height: 7, borderRadius: 99, background: sevDot(a.sev), marginTop: 5, flexShrink: 0 }} />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{a.title}</div>
                    <div style={{ fontSize: 11.5, color: 'var(--fg3,#71717a)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{a.detail}</div>
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--fg4,#52525b)', whiteSpace: 'nowrap' }}>{a.ts ? relativeTime(a.ts) : ''}</span>
                </div>
              ))}
              <div
                onClick={() => { setBellOpen(false); onNavigate('alerts'); }}
                style={{ padding: '9px 14px', fontSize: 12.5, color: 'var(--fg2,#a1a1aa)', cursor: 'pointer', textAlign: 'center' }}
                onMouseEnter={e => { e.currentTarget.style.background = 'var(--hover,#18181b)'; e.currentTarget.style.color = 'var(--fg,#fafafa)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = ''; e.currentTarget.style.color = 'var(--fg2,#a1a1aa)'; }}
              >
                View all alerts →
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Search dropdown — filters the full issues list client-side (exc/msg/service,
// case-insensitive), mirroring the design's visibleGroups() logic.
function SearchDropdown({ q, issues, onNavigate }) {
  const ql = q.toLowerCase();

  const results = (issues || [])
    .filter(g => g.exc.toLowerCase().includes(ql) || g.msg.toLowerCase().includes(ql) || g.service.includes(ql))
    .slice(0, 6)
    .map(g => ({
      fp: g.fp, exc: g.exc, msg: g.msg, service: g.service,
      dot: g.status === 'resolved' ? 'var(--fg5,#3f3f46)' : g.spiking ? RED : g.status === 'regressed' ? AMBER : ACCENT,
    }));

  return (
    <div style={{
      position: 'absolute', top: 38, right: 0, width: 360,
      background: 'var(--panel,#101013)',
      border: '1px solid var(--border2,#27272a)',
      borderRadius: 10, boxShadow: '0 16px 40px rgba(0,0,0,0.55)',
      zIndex: 70, padding: 4,
    }}>
      {results.map(r => (
        <div
          key={r.fp}
          onMouseDown={() => onNavigate('issues', r.fp)}
          style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 7, cursor: 'pointer' }}
          onMouseEnter={e => { e.currentTarget.style.background = 'var(--hover,#18181b)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = ''; }}
        >
          <span style={{ width: 6, height: 6, borderRadius: 99, background: r.dot, flexShrink: 0 }} />
          <span style={{ fontSize: 12.5, fontWeight: 600, whiteSpace: 'nowrap' }}>{r.exc}</span>
          <span style={{ fontFamily: "'Geist Mono',monospace", fontSize: 11.5, color: 'var(--fg3,#71717a)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1 }}>{r.msg}</span>
          <span style={{ fontSize: 11, color: 'var(--fg4,#52525b)', whiteSpace: 'nowrap' }}>{r.service}</span>
        </div>
      ))}
      {results.length === 0 && (
        <div style={{ padding: '12px 10px', fontSize: 12.5, color: 'var(--fg4,#52525b)' }}>No issues match "{q}".</div>
      )}
    </div>
  );
}
