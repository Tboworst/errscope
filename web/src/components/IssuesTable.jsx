import React from 'react';
import { ACCENT, dotColor, tagProps, envStyle, mkSpark, RED, MUTED } from '../styles.js';
import { relativeTime, fmtCount } from '../format.js';

export default function IssuesTable({ issues, sheetFp, onOpenSheet, onMenu, rowPad }) {
  const rows = issues.map(g => {
    const resolved = g.status === 'resolved';
    const spike = g.spiking && !resolved;
    const { tag, tagColor, tagBg } = tagProps(g.status, g.spiking);
    const { envColor, envBg } = envStyle(g.env);
    const trendColor = resolved ? 'var(--border2,#27272a)' : spike ? RED : 'var(--fg5,#3f3f46)';
    const trend = mkSpark(g.trend || [], trendColor);

    return {
      fp: g.fp,
      exc: g.exc,
      msg: g.msg,
      dotColor: dotColor(g.status, g.spiking),
      tag, tagColor, tagBg,
      trend,
      count: fmtCount(g.count),
      countColor: resolved ? MUTED : spike ? '#fca5a5' : 'var(--fg,#fafafa)',
      service: g.service,
      env: g.env, envColor, envBg,
      last: g.last_seen ? relativeTime(g.last_seen) : '—',
      opacity: resolved ? 0.55 : 1,
      bg: sheetFp === g.fp ? 'var(--panel,#101013)' : 'transparent',
    };
  });

  return (
    <div style={{ border: '1px solid var(--border,#1f1f23)', borderRadius: 12, overflowX: 'auto' }}>
      {/* Header */}
      <div style={{
        display: 'grid', minWidth: 900,
        gridTemplateColumns: 'minmax(220px,1fr) 110px 64px 116px 92px 88px 28px',
        gap: '0 16px', padding: '10px 16px',
        borderBottom: '1px solid var(--border,#1f1f23)',
        fontSize: 11.5, color: 'var(--fg3,#71717a)', fontWeight: 500,
        textTransform: 'uppercase', letterSpacing: '0.4px',
      }}>
        <div>Issue</div><div>Trend</div><div>Events</div><div>Service</div><div>Env</div><div>Last seen</div><div></div>
      </div>

      {rows.map(item => (
        <IssueRow key={item.fp} item={item} rowPad={rowPad} onOpenSheet={onOpenSheet} onMenu={onMenu} />
      ))}

      {rows.length === 0 && (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--fg4,#52525b)', fontSize: 13 }}>
          No issues match the current filters.
        </div>
      )}
    </div>
  );
}

function IssueRow({ item, rowPad, onOpenSheet, onMenu }) {
  const [hovered, setHovered] = React.useState(false);

  return (
    <div
      onClick={() => onOpenSheet(item.fp)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'grid', minWidth: 900,
        gridTemplateColumns: 'minmax(220px,1fr) 110px 64px 116px 92px 88px 28px',
        gap: '0 16px', padding: `${rowPad} 16px`,
        borderBottom: '1px solid var(--divider,#17171a)',
        cursor: 'pointer', alignItems: 'center',
        background: hovered ? 'var(--panel,#101013)' : item.bg,
        opacity: item.opacity,
      }}
    >
      {/* Issue column */}
      <div style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <span style={{ width: 7, height: 7, borderRadius: 99, background: item.dotColor, flexShrink: 0 }} />
          <span style={{ fontWeight: 600, fontSize: 13.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.exc}</span>
          {item.tag && (
            <span style={{
              fontSize: 10.5, fontWeight: 600, color: item.tagColor, background: item.tagBg,
              borderRadius: 99, padding: '1px 8px', flexShrink: 0,
            }}>
              {item.tag}
            </span>
          )}
        </div>
        <div style={{
          fontFamily: "'Geist Mono',monospace", fontSize: 12, color: 'var(--fg3,#71717a)',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          marginTop: 3, paddingLeft: 15,
        }}>
          {item.msg}
        </div>
      </div>

      {/* Trend sparkline */}
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 24 }}>
        {item.trend.map((t, i) => (
          <div key={i} style={{ width: 4, borderRadius: 2, background: t.color, height: t.h + '%', minHeight: 2 }} />
        ))}
      </div>

      {/* Count */}
      <div style={{ fontWeight: 600, fontSize: 13.5, color: item.countColor }}>{item.count}</div>

      {/* Service */}
      <div>
        <span style={{
          fontFamily: "'Geist Mono',monospace", fontSize: 11.5, color: 'var(--fg2,#a1a1aa)',
          background: 'var(--hover,#18181b)', border: '1px solid var(--border2,#27272a)',
          borderRadius: 6, padding: '2px 8px', whiteSpace: 'nowrap',
        }}>
          {item.service}
        </span>
      </div>

      {/* Env */}
      <div>
        <span style={{
          fontSize: 11.5, fontWeight: 500, color: item.envColor, background: item.envBg,
          borderRadius: 99, padding: '2px 9px',
        }}>
          {item.env}
        </span>
      </div>

      {/* Last seen */}
      <div style={{ fontSize: 12.5, color: 'var(--fg3,#71717a)', whiteSpace: 'nowrap' }}>{item.last}</div>

      {/* Menu button */}
      <MenuBtn onClick={e => onMenu(e, item.fp)} />
    </div>
  );
}

function MenuBtn({ onClick }) {
  const [hov, setHov] = React.useState(false);
  return (
    <div
      onClick={onClick}
      title="Actions"
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        width: 24, height: 24, borderRadius: 6,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        cursor: 'pointer',
        color: hov ? 'var(--fg,#fafafa)' : 'var(--fg4,#52525b)',
        background: hov ? 'var(--border,#1f1f23)' : 'transparent',
        fontSize: 15,
      }}
    >
      ⋯
    </div>
  );
}
