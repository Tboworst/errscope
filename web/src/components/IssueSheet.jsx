import React from 'react';
import { tagProps, envStyle, MONO } from '../styles.js';
import { shortDate, relativeTime, fmtCost, fmtCount } from '../format.js';

export default function IssueSheet({ issue, onClose, onResolve, onReopen, onGithub }) {
  if (!issue) return null;

  const resolved = issue.status === 'resolved';
  const regressed = issue.status === 'regressed';
  const spike = issue.spiking && !resolved;
  const { tag, tagColor, tagBg } = tagProps(issue.status, issue.spiking);

  const chain = (issue.chain || []).map((name, i) => ({
    name, arrow: i === 0 ? '' : '↳ ', pad: (i * 14) + 'px',
  }));

  const { envColor } = envStyle(issue.env);

  const meta = [
    { label: 'Service', value: issue.service, color: 'var(--fg,#fafafa)', font: MONO },
    { label: 'Environment', value: issue.env, color: envColor, font: 'inherit' },
    { label: 'First seen', value: issue.first_seen ? shortDate(issue.first_seen) : '—', color: 'var(--fg,#fafafa)', font: 'inherit' },
    { label: 'Last seen', value: issue.last_seen ? relativeTime(issue.last_seen) : '—', color: 'var(--fg,#fafafa)', font: 'inherit' },
    { label: 'Events', value: fmtCount(issue.count), color: 'var(--fg,#fafafa)', font: 'inherit' },
    { label: 'Fingerprint', value: issue.fp, color: 'var(--fg3,#71717a)', font: MONO },
  ];

  const llm = issue.llm;
  const github = issue.github;

  const resolveLabel = resolved ? 'Resolved ✓' : 'Resolve';
  const resolveBg = resolved ? 'var(--border,#1f1f23)' : 'var(--fg,#fafafa)';
  const resolveColor = resolved ? 'var(--fg3,#71717a)' : 'var(--bg,#09090b)';
  const resolveCursor = resolved ? 'default' : 'pointer';

  const githubLabel = github ? `Issue #${github.n} ↗` : 'Create GitHub issue';

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
        zIndex: 50, display: 'flex', justifyContent: 'flex-end',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: 480, maxWidth: '92vw', height: '100%',
          background: 'var(--sheet,#0c0c0e)',
          borderLeft: '1px solid var(--border2,#27272a)',
          display: 'flex', flexDirection: 'column',
          animation: 'sheetIn 0.18s ease-out',
        }}
      >
        {/* Header */}
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border,#1f1f23)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ fontSize: 17, fontWeight: 600, letterSpacing: '-0.2px' }}>{issue.exc}</div>
            {tag && (
              <span style={{ fontSize: 10.5, fontWeight: 600, color: tagColor, background: tagBg, borderRadius: 99, padding: '2px 9px' }}>
                {tag}
              </span>
            )}
            <div
              onClick={onClose}
              style={{ marginLeft: 'auto', width: 28, height: 28, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: 'var(--fg3,#71717a)' }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--hover,#18181b)'; e.currentTarget.style.color = 'var(--fg,#fafafa)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = ''; e.currentTarget.style.color = 'var(--fg3,#71717a)'; }}
            >
              ✕
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
            <div
              onClick={resolved ? undefined : onResolve}
              style={{
                background: resolveBg, color: resolveColor,
                fontWeight: 600, fontSize: 13, borderRadius: 8,
                padding: '7px 14px', cursor: resolveCursor, whiteSpace: 'nowrap',
              }}
            >
              {resolveLabel}
            </div>
            <div
              onClick={onGithub}
              style={{
                border: '1px solid var(--border2,#27272a)', color: 'var(--fg1,#d4d4d8)',
                fontWeight: 500, fontSize: 13, borderRadius: 8,
                padding: '7px 14px', cursor: 'pointer', whiteSpace: 'nowrap',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--hover,#18181b)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = ''; }}
            >
              {githubLabel}
            </div>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
          <SectionLabel>Message</SectionLabel>
          <div style={{
            fontFamily: MONO, fontSize: 12.5, color: 'var(--fg0,#e4e4e7)',
            background: 'var(--code,#131316)', border: '1px solid var(--border,#1f1f23)',
            borderRadius: 10, padding: '12px 14px', lineHeight: 1.6,
          }}>
            {issue.msg}
          </div>

          <SectionLabel style={{ margin: '20px 0 8px 0' }}>Call chain</SectionLabel>
          <div style={{
            background: 'var(--code,#131316)', border: '1px solid var(--border,#1f1f23)',
            borderRadius: 10, padding: '12px 14px',
            display: 'flex', flexDirection: 'column', gap: 4,
          }}>
            {chain.map((fn, i) => (
              <div key={i} style={{ fontFamily: MONO, fontSize: 12.5, color: 'var(--fg2,#a1a1aa)', paddingLeft: fn.pad }}>
                <span style={{ color: 'var(--fg4,#52525b)' }}>{fn.arrow}</span>
                {fn.name}
                <span style={{ color: 'var(--fg4,#52525b)' }}>()</span>
              </div>
            ))}
          </div>

          {/* Meta grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px 20px', marginTop: 20 }}>
            {meta.map(m => (
              <div key={m.label}>
                <div style={{ fontSize: 11.5, color: 'var(--fg3,#71717a)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.4px' }}>{m.label}</div>
                <div style={{ fontSize: 13, marginTop: 4, color: m.color, fontFamily: m.font, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.value}</div>
              </div>
            ))}
          </div>

          {/* LLM correlation box */}
          {llm && (
            <div style={{ border: '1px solid var(--border,#1f1f23)', borderRadius: 10, padding: '14px 16px', marginTop: 20 }}>
              <div style={{ fontSize: 11.5, color: 'var(--fg3,#71717a)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                AI activity during spike
              </div>
              <div style={{ display: 'flex', gap: 24, marginTop: 10 }}>
                <div>
                  <div style={{ fontSize: 17, fontWeight: 600 }}>{llm.calls}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--fg3,#71717a)' }}>calls</div>
                </div>
                <div>
                  <div style={{ fontSize: 17, fontWeight: 600 }}>{fmtCost(llm.cost_usd)}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--fg3,#71717a)' }}>cost</div>
                </div>
                <div>
                  <div style={{ fontSize: 17, fontWeight: 600, color: '#ef4444' }}>{llm.errors}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--fg3,#71717a)' }}>LLM errors</div>
                </div>
              </div>
            </div>
          )}

          {/* GitHub link */}
          {github && (
            <div style={{ marginTop: 20, fontSize: 13 }}>
              <span style={{ color: 'var(--fg3,#71717a)' }}>Linked issue&nbsp;&nbsp;</span>
              <a href={github.url} target="_blank" rel="noreferrer" style={{ color: '#93c5fd' }}>
                #{github.n}
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SectionLabel({ children, style }) {
  return (
    <div style={{
      fontSize: 11.5, color: 'var(--fg3,#71717a)', fontWeight: 500,
      textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 8,
      ...style,
    }}>
      {children}
    </div>
  );
}
