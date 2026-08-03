import React from 'react';
import { ACCENT, mkBars, RED } from '../styles.js';
import { fmtCount } from '../format.js';
import { relativeTime } from '../format.js';

export default function StatCards({ page, overview, llm, deploys, alerts }) {
  const cards = buildCards(page, overview, llm, deploys, alerts);
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 20 }}>
      {cards.map((s, i) => (
        <StatCard key={i} {...s} />
      ))}
    </div>
  );
}

function StatCard({ label, value, sub, delta, deltaColor, spark }) {
  return (
    <div style={{
      border: '1px solid var(--border,#1f1f23)', borderRadius: 12,
      padding: '14px 16px', minWidth: 0, display: 'flex', flexDirection: 'column',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ fontSize: 12, color: 'var(--fg3,#71717a)', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</div>
        {delta && <div style={{ fontSize: 11.5, color: deltaColor, fontWeight: 500, whiteSpace: 'nowrap' }}>{delta}</div>}
      </div>
      <div style={{ fontSize: 24, fontWeight: 600, letterSpacing: '-0.5px', lineHeight: 1, marginTop: 8 }}>{value}</div>
      {sub && <div style={{ fontSize: 11.5, color: 'var(--fg4,#52525b)', marginTop: 5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sub}</div>}
      {spark && spark.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 30, marginTop: 'auto', paddingTop: 10 }}>
          {spark.map((v, i) => (
            <div key={i} style={{ flex: 1, borderRadius: 2, background: v.color, height: v.h + '%', minHeight: 2 }} />
          ))}
        </div>
      )}
    </div>
  );
}

function buildCards(page, overview, llm, deploys, alerts) {
  if (page === 'llm') {
    const groups = llm?.groups || [];
    const totals = llm?.totals || {};
    const calls = totals.calls || 0;
    const cost = totals.cost_usd || 0;
    const errs = totals.errors || 0;
    const lat = totals.avg_latency_ms || 0;
    const callsDaily = llm?.calls_daily || [];
    const costDaily = llm?.cost_daily || [];
    const errDaily = llm?.errors_daily || [];
    const latDaily = llm?.latency_daily || [];

    return [
      { label: 'Total calls (30d)', value: fmtCount(calls), sub: `across ${groups.length} features`, spark: mkBars(callsDaily.length ? callsDaily : [0], 'var(--fg5,#3f3f46)', ACCENT) },
      { label: 'Total cost (30d)', value: '$' + cost.toFixed(2), sub: 'ranked by spend', spark: mkBars(costDaily.length ? costDaily : [0], 'var(--fg5,#3f3f46)', '#fcd34d') },
      { label: 'LLM errors', value: String(errs), sub: '', spark: mkBars(errDaily.length ? errDaily : [0], 'var(--fg5,#3f3f46)', '#ef4444') },
      { label: 'Avg latency', value: fmtCount(lat) + ' ms', sub: 'weighted by calls', spark: mkBars(latDaily.length ? latDaily : [0], 'var(--fg5,#3f3f46)', '#86efac') },
    ];
  }

  if (page === 'alerts') {
    const live = (alerts?.alerts || []).length;
    const spikes = (alerts?.alerts || []).filter(a => a.sev === 'spike').length;
    const regs = (alerts?.alerts || []).filter(a => a.sev === 'regression').length;
    const slack = alerts?.slack_connected ? 'Connected' : 'Not set';
    const slackSub = alerts?.slack_connected ? 'SLACK_WEBHOOK_URL set' : 'Add SLACK_WEBHOOK_URL';
    return [
      { label: 'Live signals', value: String(live), sub: 'derived from current data', spark: mkBars([0,1,0,2,1,0,1,0,3,1,0,2,1,live], 'var(--fg5,#3f3f46)', '#ef4444') },
      { label: 'Spikes', value: String(spikes), delta: 'active', deltaColor: '#fca5a5', sub: '', spark: mkBars([0,0,1,0,0,1,0,0,0,1,0,1,1,spikes], 'var(--fg5,#3f3f46)', '#ef4444') },
      { label: 'Regressions', value: String(regs), sub: '', spark: mkBars([0,0,0,0,1,0,0,0,0,0,0,0,0,regs], 'var(--fg5,#3f3f46)', '#f59e0b') },
      { label: 'Slack webhook', value: slack, sub: slackSub, spark: mkBars([1,2,1,1,2,1,2,1,1,2,1,2,1,2], '#14532d', '#22c55e') },
    ];
  }

  if (page === 'deploys') {
    const deps = deploys?.deploys || [];
    const stats = deploys?.stats || {};
    const last = deps[0];
    const lastAge = last ? relativeTime(last.deployed_at) : '—';
    const lastSub = last ? `${last.service} · ${last.env}` : '';
    const errAfter = stats.errors_after_last ?? (last?.errors_after ?? 0);
    return [
      { label: 'Deploys (7d)', value: String(stats.deploys_7d ?? deps.length), sub: `${stats.services ?? 0} services`, spark: mkBars([1,0,1,0,0,2,1,0,1,0,1,0,0,stats.deploys_7d ?? deps.length], 'var(--fg5,#3f3f46)', '#22c55e') },
      { label: 'Services', value: String(stats.services ?? 0), sub: '', spark: mkBars([2,3,2,3,2,3,3,2,3,2,3,3,2,stats.services ?? 0], 'var(--fg5,#3f3f46)', ACCENT) },
      { label: 'Errors after last deploy', value: String(errAfter), delta: errAfter > 50 ? 'spike' : null, deltaColor: '#fca5a5', sub: last ? `${last.version} · ${lastAge}` : '', spark: mkBars([1,2,1,3,2,4,3,5,8,11,14,18,22,errAfter], 'var(--fg5,#3f3f46)', '#ef4444') },
      { label: 'Last deploy', value: lastAge, sub: lastSub, spark: mkBars([0,1,0,0,1,0,1,0,0,1,0,1,0,1], 'var(--fg5,#3f3f46)', '#22c55e') },
    ];
  }

  // Issues page
  const ov = overview || {};
  const eventsDaily = ov.events_daily || [];
  const activeDaily = ov.active_daily || [];
  const resolvedDaily = ov.resolved_daily || [];
  const evSpark = ov.events_spark || [];
  const max = Math.max(...evSpark, 1);
  const lastVal = evSpark[evSpark.length - 1] || 0;

  return [
    {
      label: 'Total events',
      value: fmtCount(ov.total_events || 0),
      sub: 'raw events kept 30d',
      spark: mkBars(eventsDaily.length ? eventsDaily : [0], 'var(--fg5,#3f3f46)', ACCENT),
    },
    {
      label: 'Active issues',
      value: String(ov.active_issues || 0),
      sub: `${ov.spiking_count || 0} spiking · ${ov.regressed_count || 0} regression`,
      spark: mkBars(activeDaily.length ? activeDaily : [0], 'var(--fg5,#3f3f46)', '#f59e0b'),
    },
    {
      label: 'Resolved (30d)',
      value: String(ov.resolved_30d || 0),
      sub: '',
      spark: mkBars(resolvedDaily.length ? resolvedDaily : [0], '#14532d', '#22c55e'),
    },
    {
      label: 'Events / min',
      value: String(ov.events_per_min ?? lastVal),
      sub: `peak ${max} · last 20m`,
      spark: evSpark.map(v => ({ h: Math.round(100 * v / max), color: v === max ? RED : ACCENT })),
    },
  ];
}
