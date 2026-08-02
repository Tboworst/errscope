import React from 'react';
import { ACCENT, MONO } from '../styles.js';

const NAV_DEFS = [
  { id: 'issues', label: 'Issues', icon: '◧' },
  { id: 'llm', label: 'LLM Calls', icon: '✦' },
  { id: 'alerts', label: 'Alerts', icon: '◎' },
  { id: 'deploys', label: 'Deploys', icon: '⇪' },
];

export default function Sidebar({ page, collapsed, onNavigate, onToggle, meta, envFilter, onEnvFilter, activeIssueCount, alertCount }) {
  const open = !collapsed;
  const sideWidth = open ? '232px' : '64px';
  const sidePad = open ? '16px 12px' : '16px 9px';
  const headDir = open ? 'row' : 'column';
  const navJustify = open ? 'flex-start' : 'center';
  const navPad = open ? '7px 10px' : '8px 0';
  const toggleIcon = open ? '«' : '»';
  const toggleMargin = open ? 'auto' : '0';

  const services = meta?.services || [];
  const envs = meta?.envs || [];
  const health = meta?.health || {};
  const dbMb = health.db_bytes ? (health.db_bytes / 1e6).toFixed(1) : '—';
  const host = health.host || 'localhost:7000';
  const eventCount = health.event_count ?? 0;
  const retentionDays = health.retention_days ?? 30;
  const storageUsedPct = health.db_bytes ? Math.round(health.db_bytes / 1e7) : 0; // rough pct of 10MB cap

  // Compute issue counts per env from meta.envs
  const envCounts = {};
  envs.forEach(e => { envCounts[e.name] = e.count; });

  const envRows = ['production', 'staging'].map(env => {
    const active = envFilter === env;
    return {
      name: env,
      dot: env === 'production' ? '#ef4444' : '#f59e0b',
      count: String(envCounts[env] || 0),
      bg: active ? 'var(--hover,#18181b)' : 'transparent',
      color: active ? 'var(--fg,#fafafa)' : 'var(--fg2,#a1a1aa)',
      onClick: () => onEnvFilter(active ? null : env),
    };
  });

  // Badge counts for nav items — derived from live data (empty string hides the badge)
  const badges = {
    issues: activeIssueCount > 0 ? String(activeIssueCount) : '',
    llm: '',
    alerts: alertCount > 0 ? String(alertCount) : '',
    deploys: '',
  };

  return (
    <div style={{
      width: sideWidth, flexShrink: 0,
      borderRight: '1px solid var(--border,#1f1f23)',
      display: 'flex', flexDirection: 'column', padding: sidePad,
      transition: 'width 0.15s ease', overflowX: 'hidden', overflowY: 'auto',
    }}>
      {/* Logo row */}
      <div style={{ display: 'flex', flexDirection: headDir, alignItems: 'center', gap: 10, padding: '4px 4px 18px 4px' }}>
        <div style={{
          width: 26, height: 26, borderRadius: 8, background: ACCENT,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontWeight: 700, color: 'var(--bg,#09090b)', fontSize: 14, flexShrink: 0,
        }}>B</div>
        {open && (
          <>
            <div style={{ fontWeight: 600, fontSize: 15, letterSpacing: '-0.2px' }}>Beacon</div>
            <div style={{
              fontSize: 10.5, color: 'var(--fg3,#71717a)',
              border: '1px solid var(--border2,#27272a)', borderRadius: 99,
              padding: '1px 7px', whiteSpace: 'nowrap',
            }}>self-hosted</div>
          </>
        )}
        <div
          onClick={onToggle}
          title="Toggle sidebar"
          style={{
            marginLeft: toggleMargin, width: 22, height: 22, borderRadius: 6,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', color: 'var(--fg3,#71717a)', fontSize: 13, flexShrink: 0,
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'var(--hover,#18181b)'; e.currentTarget.style.color = 'var(--fg,#fafafa)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = ''; e.currentTarget.style.color = 'var(--fg3,#71717a)'; }}
        >
          {toggleIcon}
        </div>
      </div>

      {/* Nav items */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {NAV_DEFS.map(n => {
          const active = page === n.id;
          return (
            <div
              key={n.id}
              onClick={() => onNavigate(n.id)}
              title={n.label}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: navJustify,
                gap: 10, padding: navPad, borderRadius: 8, cursor: 'pointer',
                background: active ? 'var(--hover,#18181b)' : 'transparent',
                color: active ? 'var(--fg,#fafafa)' : 'var(--fg2,#a1a1aa)',
                fontWeight: active ? 600 : 400,
              }}
              onMouseEnter={e => { if (!active) { e.currentTarget.style.background = 'var(--hover,#18181b)'; e.currentTarget.style.color = 'var(--fg,#fafafa)'; } }}
              onMouseLeave={e => { if (!active) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--fg2,#a1a1aa)'; } }}
            >
              <span style={{ width: 16, textAlign: 'center', fontSize: 13, opacity: 0.9, flexShrink: 0 }}>{n.icon}</span>
              {open && (
                <>
                  <span style={{ whiteSpace: 'nowrap' }}>{n.label}</span>
                  {badges[n.id] && (
                    <span style={{
                      marginLeft: 'auto', background: 'var(--border2,#27272a)', color: 'var(--fg1,#d4d4d8)',
                      borderRadius: 99, fontSize: 11, padding: '1px 8px', fontWeight: 500,
                    }}>{badges[n.id]}</span>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* Environments */}
      {open && (
        <div style={{ marginTop: 22, padding: '0 10px' }}>
          <div style={{ fontSize: 10.5, color: 'var(--fg4,#52525b)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 6 }}>
            Environments
          </div>
          {envRows.map(ev => (
            <div
              key={ev.name}
              onClick={ev.onClick}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '5px 8px', margin: '0 -8px', borderRadius: 7,
                cursor: 'pointer', background: ev.bg, color: ev.color,
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--hover,#18181b)'; e.currentTarget.style.color = 'var(--fg,#fafafa)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = ev.bg; e.currentTarget.style.color = ev.color; }}
            >
              <span style={{ width: 7, height: 7, borderRadius: 99, background: ev.dot, flexShrink: 0 }} />
              <span style={{ fontSize: 12.5, flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{ev.name}</span>
              <span style={{ fontSize: 11, color: 'var(--fg4,#52525b)' }}>{ev.count}</span>
            </div>
          ))}
        </div>
      )}

      {/* Services */}
      {open && services.length > 0 && (
        <div style={{ marginTop: 22, padding: '0 10px' }}>
          <div style={{ fontSize: 10.5, color: 'var(--fg4,#52525b)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 8 }}>
            Services
          </div>
          {services.slice(0, 6).map(sv => (
            <div key={sv.name} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
              <span style={{ fontFamily: MONO, fontSize: 12, color: 'var(--fg2,#a1a1aa)', flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sv.name}</span>
              <span style={{ fontSize: 11, color: 'var(--fg4,#52525b)' }}>{sv.count}</span>
            </div>
          ))}
        </div>
      )}

      {/* Bottom: health card + instance menu */}
      <div style={{ marginTop: 'auto', paddingTop: 20, display: 'flex', flexDirection: 'column', gap: 10, flexShrink: 0 }}>
        {open && (
          <div style={{ border: '1px solid var(--border,#1f1f23)', borderRadius: 10, padding: '10px 12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ position: 'relative', width: 8, height: 8, flexShrink: 0 }}>
                <span style={{ position: 'absolute', inset: 0, borderRadius: 99, background: '#22c55e' }} />
                <span style={{ position: 'absolute', inset: 0, borderRadius: 99, background: '#22c55e', animation: 'pingDot 2s ease-out infinite' }} />
              </span>
              <span style={{ fontSize: 12.5, color: 'var(--fg1,#d4d4d8)', whiteSpace: 'nowrap' }}>Ingest healthy</span>
            </div>
            <div style={{ fontFamily: MONO, fontSize: 11, color: 'var(--fg4,#52525b)', marginTop: 8, whiteSpace: 'nowrap' }}>{host} · flask</div>
            <div style={{ fontFamily: MONO, fontSize: 11, color: 'var(--fg4,#52525b)', marginTop: 3, whiteSpace: 'nowrap' }}>beacon.db · {dbMb} MB</div>
            <div style={{ height: 4, background: 'var(--hover,#18181b)', borderRadius: 2, marginTop: 8 }}>
              <div style={{ height: 4, borderRadius: 2, background: '#22c55e', width: Math.min(storageUsedPct, 100) + '%' }} />
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--fg5,#3f3f46)', marginTop: 5, whiteSpace: 'nowrap' }}>
              {eventCount.toLocaleString()} events · {retentionDays}d retention
            </div>
          </div>
        )}
        <InstanceMenu open={open} navJustify={navJustify} />
      </div>
    </div>
  );
}

function InstanceMenu({ open, navJustify }) {
  const [menuOpen, setMenuOpen] = React.useState(false);

  const items = [
    {
      label: 'Copy ingest key', color: 'var(--fg1,#d4d4d8)',
      onClick: () => {
        setMenuOpen(false);
        navigator.clipboard.writeText('bcn_live_9f2ac81e4b').catch(() => {});
      },
    },
    {
      label: 'Copy curl example', color: 'var(--fg1,#d4d4d8)',
      onClick: () => {
        setMenuOpen(false);
        navigator.clipboard.writeText("curl -X POST http://localhost:7000/ingest -H 'Content-Type: application/json' -H 'X-Api-Key: ...'").catch(() => {});
      },
    },
    {
      label: 'Docs ↗', color: 'var(--fg1,#d4d4d8)',
      onClick: () => { setMenuOpen(false); window.open('https://github.com/PaoloJN/beacon', '_blank'); },
    },
  ];

  React.useEffect(() => {
    if (!menuOpen) return;
    const handler = () => setMenuOpen(false);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [menuOpen]);

  return (
    <div style={{ position: 'relative' }}>
      <div
        onClick={e => { e.stopPropagation(); setMenuOpen(v => !v); }}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: navJustify,
          gap: 10, padding: '6px 4px', borderRadius: 8, cursor: 'pointer',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = 'var(--hover,#18181b)'; }}
        onMouseLeave={e => { e.currentTarget.style.background = ''; }}
      >
        <div style={{
          width: 26, height: 26, borderRadius: 99,
          background: 'var(--border2,#27272a)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 12, color: 'var(--fg2,#a1a1aa)', flexShrink: 0,
        }}>⚙</div>
        {open && (
          <>
            <div style={{ fontSize: 12.5, color: 'var(--fg2,#a1a1aa)', whiteSpace: 'nowrap', flex: 1 }}>Instance</div>
            <span style={{ fontSize: 10, color: 'var(--fg4,#52525b)' }}>▲</span>
          </>
        )}
      </div>

      {menuOpen && (
        <div
          onClick={e => e.stopPropagation()}
          style={{
            position: 'absolute', bottom: 42, left: 0, width: 200,
            background: 'var(--panel,#101013)',
            border: '1px solid var(--border2,#27272a)',
            borderRadius: 10, boxShadow: '0 16px 40px rgba(0,0,0,0.55)',
            zIndex: 70, padding: 4,
          }}
        >
          <div style={{ padding: '8px 10px', borderBottom: '1px solid var(--border,#1f1f23)', marginBottom: 4 }}>
            <div style={{ fontSize: 12.5, fontWeight: 600 }}>beacon</div>
            <div style={{ fontFamily: "'Geist Mono',monospace", fontSize: 11, color: 'var(--fg3,#71717a)', marginTop: 1 }}>localhost:7000</div>
          </div>
          {items.map(u => (
            <div
              key={u.label}
              onClick={u.onClick}
              style={{ padding: '7px 10px', borderRadius: 7, cursor: 'pointer', fontSize: 12.5, color: u.color }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--hover,#18181b)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = ''; }}
            >
              {u.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
