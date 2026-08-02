import React from 'react';
import { envStyle } from '../styles.js';
import { relativeTime } from '../format.js';
import StatCards from './StatCards.jsx';

export default function DeploysPage({ data, rowPad, onNavigate }) {
  const deps = (data?.deploys || []).map((d, i) => ({
    ...d,
    dot: d.suspect ? '#ef4444' : i === 0 ? '#22c55e' : 'var(--fg5,#3f3f46)',
    age: d.deployed_at ? relativeTime(d.deployed_at) : '—',
    errLabel: d.suspect
      ? `${d.errors_after} errors since — likely cause of spike`
      : d.errors_after > 0
        ? `${d.errors_after} errors since deploy`
        : 'no errors since deploy',
    errColor: d.errors_after >= 50 ? '#fca5a5' : d.errors_after > 0 ? 'var(--fg2,#a1a1aa)' : 'var(--fg4,#52525b)',
    ...envStyle(d.env),
  }));

  return (
    <>
      <StatCards page="deploys" deploys={data} />

      <div style={{ border: '1px solid var(--border,#1f1f23)', borderRadius: 12, overflowX: 'auto' }}>
        <div style={{
          display: 'grid', minWidth: 820,
          gridTemplateColumns: '110px 140px 92px minmax(220px,1fr) 100px 80px',
          gap: '0 16px', padding: '10px 16px',
          borderBottom: '1px solid var(--border,#1f1f23)',
          fontSize: 11.5, color: 'var(--fg3,#71717a)', fontWeight: 500,
          textTransform: 'uppercase', letterSpacing: '0.4px',
        }}>
          <div>Version</div><div>Service</div><div>Env</div><div>Impact</div><div></div><div>Deployed</div>
        </div>

        {deps.map((d, i) => (
          <DeployRow key={d.version + d.service + i} d={d} rowPad={rowPad} onNavigate={onNavigate} />
        ))}
        {deps.length === 0 && (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--fg4,#52525b)', fontSize: 13 }}>No deploys recorded.</div>
        )}
      </div>

      {/* Markers footer */}
      <div style={{
        border: '1px solid var(--border,#1f1f23)', borderRadius: 12,
        padding: '14px 16px', marginTop: 16,
        display: 'flex', alignItems: 'baseline', gap: 12, overflowX: 'auto',
      }}>
        <span style={{ fontSize: 12, color: 'var(--fg3,#71717a)', fontWeight: 500, whiteSpace: 'nowrap' }}>Deploy markers</span>
        <span style={{ fontFamily: "'Geist Mono',monospace", fontSize: 11, color: 'var(--fg4,#52525b)', whiteSpace: 'nowrap' }}>
          {`POST /deploy {"service": "…", "environment": "…", "version": "…"}`}
        </span>
      </div>
    </>
  );
}

function DeployRow({ d, rowPad, onNavigate }) {
  const [hov, setHov] = React.useState(false);

  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'grid', minWidth: 820,
        gridTemplateColumns: '110px 140px 92px minmax(220px,1fr) 100px 80px',
        gap: '0 16px', padding: `${rowPad} 16px`,
        borderBottom: '1px solid var(--divider,#17171a)',
        alignItems: 'center',
        background: hov ? 'var(--panel,#101013)' : 'transparent',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        <span style={{ width: 7, height: 7, borderRadius: 99, background: d.dot, flexShrink: 0 }} />
        <span style={{ fontFamily: "'Geist Mono',monospace", fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap' }}>{d.version}</span>
      </div>
      <div><span style={{ fontFamily: "'Geist Mono',monospace", fontSize: 11.5, color: 'var(--fg2,#a1a1aa)', background: 'var(--hover,#18181b)', border: '1px solid var(--border2,#27272a)', borderRadius: 6, padding: '2px 8px', whiteSpace: 'nowrap' }}>{d.service}</span></div>
      <div><span style={{ fontSize: 11.5, fontWeight: 500, color: d.envColor, background: d.envBg, borderRadius: 99, padding: '2px 9px' }}>{d.env}</span></div>
      <div style={{ fontSize: 12.5, color: d.errColor, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{d.errLabel}</div>
      <div>
        {d.suspect && d.suspect_fp && (
          <span
            onClick={e => { e.stopPropagation(); onNavigate('issues', d.suspect_fp); }}
            style={{ fontSize: 12, color: '#fca5a5', cursor: 'pointer', whiteSpace: 'nowrap' }}
            onMouseEnter={e => { e.currentTarget.style.textDecoration = 'underline'; }}
            onMouseLeave={e => { e.currentTarget.style.textDecoration = 'none'; }}
          >
            View issue →
          </span>
        )}
      </div>
      <div style={{ fontSize: 12.5, color: 'var(--fg3,#71717a)', whiteSpace: 'nowrap' }}>{d.age}</div>
    </div>
  );
}
