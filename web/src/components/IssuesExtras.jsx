import React from 'react';
import { ACCENT, sevDot, envStyle } from '../styles.js';
import { relativeTime } from '../format.js';

export default function IssuesExtras({ alerts, deploys, meta }) {
  const alertsFeed = (alerts?.alerts || []).slice(0, 5);

  const deploysFeed = (deploys?.deploys || []).slice(0, 6).map(d => ({
    ...d,
    dot: d.suspect ? '#ef4444' : 'var(--fg5,#3f3f46)',
    age: d.deployed_at ? relativeTime(d.deployed_at) : '—',
  }));

  const services = meta?.services || [];
  const svcMax = Math.max(...services.map(s => s.count), 1);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 12, marginTop: 16 }}>
      {/* Latest alerts */}
      <div style={{ border: '1px solid var(--border,#1f1f23)', borderRadius: 12, padding: '14px 16px' }}>
        <div style={{ fontSize: 12, color: 'var(--fg3,#71717a)', fontWeight: 500, marginBottom: 8 }}>Latest alerts</div>
        {alertsFeed.map((a, i) => (
          <div key={i} style={{ display: 'flex', gap: 10, padding: '8px 0', borderTop: '1px solid var(--divider,#17171a)', alignItems: 'flex-start' }}>
            <span style={{ width: 7, height: 7, borderRadius: 99, background: sevDot(a.sev), marginTop: 5, flexShrink: 0 }} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{a.title}</div>
              <div style={{ fontSize: 11.5, color: 'var(--fg3,#71717a)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{a.detail}</div>
            </div>
            <span style={{ fontSize: 11, color: 'var(--fg4,#52525b)', whiteSpace: 'nowrap' }}>{a.ts ? relativeTime(a.ts) : '—'}</span>
          </div>
        ))}
        {alertsFeed.length === 0 && (
          <div style={{ fontSize: 12.5, color: 'var(--fg4,#52525b)', paddingTop: 8 }}>No recent alerts.</div>
        )}
      </div>

      {/* Recent deploys */}
      <div style={{ border: '1px solid var(--border,#1f1f23)', borderRadius: 12, padding: '14px 16px' }}>
        <div style={{ fontSize: 12, color: 'var(--fg3,#71717a)', fontWeight: 500, marginBottom: 8 }}>Recent deploys</div>
        {deploysFeed.map((d, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderTop: '1px solid var(--divider,#17171a)' }}>
            <span style={{ width: 7, height: 7, borderRadius: 99, background: d.dot, flexShrink: 0 }} />
            <span style={{ fontFamily: "'Geist Mono',monospace", fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap' }}>{d.version}</span>
            <span style={{ fontSize: 12, color: 'var(--fg3,#71717a)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{d.service}</span>
            <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--fg4,#52525b)', whiteSpace: 'nowrap' }}>{d.age}</span>
          </div>
        ))}
        {deploysFeed.length === 0 && (
          <div style={{ fontSize: 12.5, color: 'var(--fg4,#52525b)', paddingTop: 8 }}>No recent deploys.</div>
        )}
      </div>

      {/* Top services */}
      <div style={{ border: '1px solid var(--border,#1f1f23)', borderRadius: 12, padding: '14px 16px' }}>
        <div style={{ fontSize: 12, color: 'var(--fg3,#71717a)', fontWeight: 500, marginBottom: 8 }}>Top services by events</div>
        {services.slice(0, 6).map(sv => (
          <div key={sv.name} style={{ padding: '8px 0', borderTop: '1px solid var(--divider,#17171a)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12.5 }}>
              <span style={{ fontFamily: "'Geist Mono',monospace", color: 'var(--fg1,#d4d4d8)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sv.name}</span>
              <span style={{ color: 'var(--fg3,#71717a)' }}>{sv.count.toLocaleString()}</span>
            </div>
            <div style={{ height: 4, background: 'var(--hover,#18181b)', borderRadius: 2, marginTop: 7 }}>
              <div style={{ height: 4, borderRadius: 2, background: ACCENT, width: Math.round(100 * sv.count / svcMax) + '%' }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
