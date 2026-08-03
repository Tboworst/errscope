import React from 'react';
import { ACCENT, envStyle } from '../styles.js';
import { relativeTime, fmtTokens, fmtCount } from '../format.js';
import StatCards from './StatCards.jsx';

export default function LlmPage({ data, envFilter, rowPad }) {
  const groups = (data?.groups || []).slice().sort((a, b) => b.cost_usd - a.cost_usd);
  const costMax = Math.max(...groups.map(g => g.cost_usd), 0.01);
  const latMax = Math.max(...groups.map(g => g.avg_latency_ms), 1);

  const costBars = groups.map(g => ({
    name: g.feature,
    cost: '$' + g.cost_usd.toFixed(2),
    w: Math.round(100 * g.cost_usd / costMax) + '%',
    color: g.cost_usd >= 10 ? '#ef4444' : g.cost_usd >= 1 ? '#f59e0b' : ACCENT,
  }));

  const tokenRows = [...groups].sort((a, b) => (b.tokens_in + b.tokens_out) - (a.tokens_in + a.tokens_out)).map(g => ({
    name: g.feature,
    tin: fmtTokens(g.tokens_in),
    tout: fmtTokens(g.tokens_out),
  }));

  const latBars = [...groups].sort((a, b) => b.avg_latency_ms - a.avg_latency_ms).map(g => ({
    name: g.feature,
    lat: fmtCount(g.avg_latency_ms) + ' ms',
    w: Math.round(100 * g.avg_latency_ms / latMax) + '%',
    color: g.avg_latency_ms >= 2000 ? '#fca5a5' : 'var(--fg2,#a1a1aa)',
    barColor: g.avg_latency_ms >= 2000 ? '#ef4444' : 'var(--fg5,#3f3f46)',
  }));

  return (
    <>
      <StatCards page="llm" llm={data} />

      {/* Table */}
      <div style={{ border: '1px solid var(--border,#1f1f23)', borderRadius: 12, overflowX: 'auto' }}>
        <div style={{
          display: 'grid', minWidth: 1030,
          gridTemplateColumns: '150px minmax(140px,1fr) 116px 92px 70px 60px 60px 80px 92px 88px',
          gap: '0 16px', padding: '10px 16px',
          borderBottom: '1px solid var(--border,#1f1f23)',
          fontSize: 11.5, color: 'var(--fg3,#71717a)', fontWeight: 500,
          textTransform: 'uppercase', letterSpacing: '0.4px',
        }}>
          <div>Model</div><div>Feature</div><div>Service</div><div>Env</div>
          <div>Calls</div><div>Errors</div><div>Err %</div><div>Latency</div><div>Cost</div><div>Last seen</div>
        </div>

        {groups.map(g => {
          const { envColor, envBg } = envStyle(g.env);
          const errPctColor = g.err_pct >= 10 ? '#fca5a5' : g.err_pct >= 2 ? '#fcd34d' : 'var(--fg2,#a1a1aa)';
          const costColor = g.cost_usd >= 10 ? '#fca5a5' : g.cost_usd >= 1 ? '#fcd34d' : 'var(--fg2,#a1a1aa)';
          return (
            <LlmRow key={g.model + g.feature} g={g} rowPad={rowPad} envColor={envColor} envBg={envBg} errPctColor={errPctColor} costColor={costColor} />
          );
        })}
        {groups.length === 0 && (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--fg4,#52525b)', fontSize: 13 }}>No LLM data.</div>
        )}
      </div>

      {/* Bottom panels */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 12, marginTop: 16 }}>
        <Panel title="Cost by feature">
          {costBars.map(c => (
            <div key={c.name} style={{ padding: '8px 0', borderTop: '1px solid var(--divider,#17171a)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12.5 }}>
                <span style={{ fontFamily: "'Geist Mono',monospace", color: 'var(--fg1,#d4d4d8)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.name}</span>
                <span style={{ fontFamily: "'Geist Mono',monospace", color: 'var(--fg3,#71717a)' }}>{c.cost}</span>
              </div>
              <BarTrack color={c.color} w={c.w} />
            </div>
          ))}
        </Panel>

        <Panel title="Token usage (30d)">
          {tokenRows.map(t => (
            <div key={t.name} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderTop: '1px solid var(--divider,#17171a)' }}>
              <span style={{ fontFamily: "'Geist Mono',monospace", fontSize: 12.5, color: 'var(--fg1,#d4d4d8)', flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.name}</span>
              <span style={{ fontSize: 11.5, color: 'var(--fg3,#71717a)', whiteSpace: 'nowrap' }}>in <span style={{ color: 'var(--fg2,#a1a1aa)' }}>{t.tin}</span></span>
              <span style={{ fontSize: 11.5, color: 'var(--fg3,#71717a)', whiteSpace: 'nowrap' }}>out <span style={{ color: 'var(--fg2,#a1a1aa)' }}>{t.tout}</span></span>
            </div>
          ))}
        </Panel>

        <Panel title="Slowest features">
          {latBars.map(l => (
            <div key={l.name} style={{ padding: '8px 0', borderTop: '1px solid var(--divider,#17171a)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12.5 }}>
                <span style={{ fontFamily: "'Geist Mono',monospace", color: 'var(--fg1,#d4d4d8)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{l.name}</span>
                <span style={{ color: l.color }}>{l.lat}</span>
              </div>
              <BarTrack color={l.barColor} w={l.w} />
            </div>
          ))}
        </Panel>
      </div>
    </>
  );
}

function LlmRow({ g, rowPad, envColor, envBg, errPctColor, costColor }) {
  const [hov, setHov] = React.useState(false);
  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'grid', minWidth: 1030,
        gridTemplateColumns: '150px minmax(140px,1fr) 116px 92px 70px 60px 60px 80px 92px 88px',
        gap: '0 16px', padding: `${rowPad} 16px`,
        borderBottom: '1px solid var(--divider,#17171a)',
        alignItems: 'center',
        background: hov ? 'var(--panel,#101013)' : 'transparent',
      }}
    >
      <div style={{ fontWeight: 600, fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{g.model}</div>
      <div style={{ fontFamily: "'Geist Mono',monospace", fontSize: 12, color: 'var(--fg2,#a1a1aa)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{g.feature}</div>
      <div><span style={{ fontFamily: "'Geist Mono',monospace", fontSize: 11.5, color: 'var(--fg2,#a1a1aa)', background: 'var(--hover,#18181b)', border: '1px solid var(--border2,#27272a)', borderRadius: 6, padding: '2px 8px', whiteSpace: 'nowrap' }}>{g.service}</span></div>
      <div><span style={{ fontSize: 11.5, fontWeight: 500, color: envColor, background: envBg, borderRadius: 99, padding: '2px 9px' }}>{g.env}</span></div>
      <div style={{ fontSize: 13 }}>{fmtCount(g.calls)}</div>
      <div style={{ fontSize: 13 }}>{g.errors}</div>
      <div style={{ fontSize: 13, fontWeight: 500, color: errPctColor }}>{g.err_pct.toFixed(1)}%</div>
      <div style={{ fontSize: 13, color: 'var(--fg2,#a1a1aa)' }}>{fmtCount(g.avg_latency_ms)} ms</div>
      <div style={{ fontFamily: "'Geist Mono',monospace", fontSize: 12.5, color: costColor }}>${g.cost_usd.toFixed(4)}</div>
      <div style={{ fontSize: 12, color: 'var(--fg3,#71717a)', whiteSpace: 'nowrap' }}>{g.last_seen ? relativeTime(g.last_seen) : '—'}</div>
    </div>
  );
}

function Panel({ title, children }) {
  return (
    <div style={{ border: '1px solid var(--border,#1f1f23)', borderRadius: 12, padding: '14px 16px' }}>
      <div style={{ fontSize: 12, color: 'var(--fg3,#71717a)', fontWeight: 500, marginBottom: 8 }}>{title}</div>
      {children}
    </div>
  );
}

function BarTrack({ color, w }) {
  return (
    <div style={{ height: 4, background: 'var(--hover,#18181b)', borderRadius: 2, marginTop: 7 }}>
      <div style={{ height: 4, borderRadius: 2, background: color, width: w }} />
    </div>
  );
}
