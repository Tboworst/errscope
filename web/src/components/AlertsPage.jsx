import React from 'react';
import { sevStyle, sevDot, envStyle } from '../styles.js';
import { relativeTime } from '../format.js';
import StatCards from './StatCards.jsx';

const ALERT_RULES = [
  { name: 'Count threshold', rule: 'group count >= 60 events' },
  { name: 'Spike', rule: '5x vs previous 5-min window (min 3)' },
  { name: 'Cold spike', rule: '0 -> 5+ events in 5 min' },
  { name: 'Regression', rule: 'resolved group fires again' },
  { name: 'LLM cost spike', rule: '5x spend, or $0 -> $0.05+' },
  { name: 'LLM error spike', rule: '5x errors vs previous window' },
  { name: 'Correlated spike', rule: 'errors + LLM cost move together' },
];

export default function AlertsPage({ data, rowPad, onNavigate }) {
  const alertRows = (data?.alerts || []).map(a => {
    const { color, bg } = sevStyle(a.sev);
    const { envColor, envBg } = envStyle(a.env || 'production');
    const action = a.link?.type === 'issue' ? 'Issue →' : a.link?.page === 'deploys' ? 'Deploys →' : 'LLM calls →';
    return { ...a, color, bg, envColor, envBg, action };
  });

  const slackConnected = data?.slack_connected;
  const rules = data?.rules || ALERT_RULES;

  return (
    <>
      <StatCards page="alerts" alerts={data} />

      <div style={{ border: '1px solid var(--border,#1f1f23)', borderRadius: 12, overflowX: 'auto' }}>
        <div style={{
          display: 'grid', minWidth: 900,
          gridTemplateColumns: 'minmax(240px,1fr) 100px 116px 92px 110px 80px',
          gap: '0 16px', padding: '10px 16px',
          borderBottom: '1px solid var(--border,#1f1f23)',
          fontSize: 11.5, color: 'var(--fg3,#71717a)', fontWeight: 500,
          textTransform: 'uppercase', letterSpacing: '0.4px',
        }}>
          <div>Alert</div><div>Type</div><div>Service</div><div>Env</div><div>Go to</div><div>Time</div>
        </div>

        {alertRows.map((a, i) => (
          <AlertRow key={a.id || i} a={a} rowPad={rowPad} onNavigate={onNavigate} />
        ))}
        {alertRows.length === 0 && (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--fg4,#52525b)', fontSize: 13 }}>No active alerts.</div>
        )}
      </div>

      {/* Rules panel */}
      <div style={{ border: '1px solid var(--border,#1f1f23)', borderRadius: 12, padding: '14px 16px', marginTop: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: 'var(--fg3,#71717a)', fontWeight: 500 }}>Alert rules</span>
          {slackConnected && (
            <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: '#86efac' }}>
              <span style={{ width: 6, height: 6, borderRadius: 99, background: '#22c55e' }} />
              Slack connected
            </span>
          )}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: '0 24px', marginTop: 6 }}>
          {rules.map(r => (
            <div key={r.name} style={{ display: 'flex', gap: 10, alignItems: 'baseline', fontSize: 12, padding: '7px 0', borderTop: '1px solid var(--divider,#17171a)' }}>
              <span style={{ color: 'var(--fg1,#d4d4d8)', whiteSpace: 'nowrap' }}>{r.name}</span>
              <span style={{ marginLeft: 'auto', fontFamily: "'Geist Mono',monospace", fontSize: 10.5, color: 'var(--fg4,#52525b)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.rule}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function AlertRow({ a, rowPad, onNavigate }) {
  const [hov, setHov] = React.useState(false);

  function handleClick() {
    if (a.link?.type === 'issue') onNavigate('issues', a.link.fp);
    else if (a.link?.page) onNavigate(a.link.page);
    else onNavigate('alerts');
  }

  return (
    <div
      onClick={handleClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'grid', minWidth: 900,
        gridTemplateColumns: 'minmax(240px,1fr) 100px 116px 92px 110px 80px',
        gap: '0 16px', padding: `${rowPad} 16px`,
        borderBottom: '1px solid var(--divider,#17171a)',
        cursor: 'pointer', alignItems: 'center',
        background: hov ? 'var(--panel,#101013)' : 'transparent',
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <span style={{ width: 7, height: 7, borderRadius: 99, background: sevDot(a.sev), flexShrink: 0 }} />
          <span style={{ fontWeight: 600, fontSize: 13.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{a.title}</span>
        </div>
        <div style={{ fontFamily: "'Geist Mono',monospace", fontSize: 12, color: 'var(--fg3,#71717a)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginTop: 3, paddingLeft: 15 }}>{a.detail}</div>
      </div>
      <div><span style={{ fontSize: 10.5, fontWeight: 600, color: a.color, background: a.bg, borderRadius: 99, padding: '1px 8px', whiteSpace: 'nowrap' }}>{a.sev}</span></div>
      <div><span style={{ fontFamily: "'Geist Mono',monospace", fontSize: 11.5, color: 'var(--fg2,#a1a1aa)', background: 'var(--hover,#18181b)', border: '1px solid var(--border2,#27272a)', borderRadius: 6, padding: '2px 8px', whiteSpace: 'nowrap' }}>{a.service}</span></div>
      <div><span style={{ fontSize: 11.5, fontWeight: 500, color: a.envColor, background: a.envBg, borderRadius: 99, padding: '2px 9px' }}>{a.env}</span></div>
      <div style={{ fontSize: 12, color: 'var(--fg4,#52525b)', whiteSpace: 'nowrap' }}>{a.action}</div>
      <div style={{ fontSize: 12.5, color: 'var(--fg3,#71717a)', whiteSpace: 'nowrap' }}>{a.ts ? relativeTime(a.ts) : '—'}</div>
    </div>
  );
}
