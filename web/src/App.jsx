import React, { useState, useEffect, useRef, useCallback } from 'react';
import { applyTheme } from './theme.js';
import { ROW_PAD } from './theme.js';
import {
  fetchIssues, fetchIssue, fetchOverview, fetchLlm, fetchDeploys, fetchAlerts, fetchMeta,
  resolveIssue, reopenIssue, createGithubIssue,
} from './api.js';

import Sidebar from './components/Sidebar.jsx';
import Header from './components/Header.jsx';
import StatCards from './components/StatCards.jsx';
import IssuesTable from './components/IssuesTable.jsx';
import IssuesExtras from './components/IssuesExtras.jsx';
import LlmPage from './components/LlmPage.jsx';
import AlertsPage from './components/AlertsPage.jsx';
import DeploysPage from './components/DeploysPage.jsx';
import IssueSheet from './components/IssueSheet.jsx';
import RowMenu from './components/RowMenu.jsx';
import Toast from './components/Toast.jsx';

const POLL_INTERVAL = 2000;

export default function App() {
  // Page / UI state
  const [page, setPage] = useState('issues');
  const [envFilter, setEnvFilter] = useState(null);
  const [showResolved, setShowResolved] = useState(false);
  const [q, setQ] = useState('');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Sheet / menu state
  const [sheetFp, setSheetFp] = useState(null);
  const [sheetIssue, setSheetIssue] = useState(null); // full issue object for the sheet
  const [menuFp, setMenuFp] = useState(null);
  const [menuPos, setMenuPos] = useState({ x: 0, y: 0 });

  // Toast
  const [toast, setToast] = useState(null);
  const toastTimerRef = useRef(null);

  // API data
  const [issues, setIssues] = useState([]);
  const [overview, setOverview] = useState(null);
  const [llmData, setLlmData] = useState(null);
  const [deploysData, setDeploysData] = useState(null);
  const [alertsData, setAlertsData] = useState(null);
  const [meta, setMeta] = useState(null);

  const notify = useCallback((msg) => {
    clearTimeout(toastTimerRef.current);
    setToast(msg);
    toastTimerRef.current = setTimeout(() => setToast(null), 3500);
  }, []);

  // Load all data
  const loadAll = useCallback(async () => {
    try {
      const [iss, ov, llm, deps, alts, mt] = await Promise.all([
        fetchIssues({ env: envFilter || undefined, q: q || undefined, include_resolved: true }),
        fetchOverview({ env: envFilter || undefined }),
        fetchLlm({ env: envFilter || undefined }),
        fetchDeploys({ env: envFilter || undefined }),
        fetchAlerts({ env: envFilter || undefined }),
        fetchMeta(),
      ]);
      setIssues(iss.issues || []);
      setOverview(ov);
      setLlmData(llm);
      setDeploysData(deps);
      setAlertsData(alts);
      setMeta(mt);
    } catch (err) {
      notify("Can't reach Beacon server");
    }
  }, [envFilter, q, notify]);

  // Re-fetch sheet issue when sheetFp changes
  useEffect(() => {
    if (!sheetFp) { setSheetIssue(null); return; }
    fetchIssue(sheetFp).then(data => setSheetIssue(data)).catch(() => {
      // fall back to list issue
      const found = issues.find(x => x.fp === sheetFp);
      if (found) setSheetIssue(found);
    });
  }, [sheetFp]);

  // Initial load + polling. loadAll's identity changes with envFilter/q
  // (useCallback deps), so this effect also re-runs on filter changes.
  useEffect(() => {
    applyTheme('zinc');
    loadAll();
    const interval = setInterval(loadAll, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [loadAll]);

  // Keyboard handlers
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== 'Escape') return;
      if (menuFp) { setMenuFp(null); return; }
      if (sheetFp) { setSheetFp(null); return; }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [menuFp, sheetFp]);

  // Click-away to close menus
  useEffect(() => {
    const handler = () => { if (menuFp) setMenuFp(null); };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [menuFp]);

  // Cleanup
  useEffect(() => {
    return () => clearTimeout(toastTimerRef.current);
  }, []);

  // Navigation helper (also handles opening sheet from search/alerts)
  const handleNavigate = useCallback((newPage, fp) => {
    setPage(newPage);
    setSheetFp(fp || null);
    setMenuFp(null);
  }, []);

  // Visible issues — client-side resolved toggle plus a local q filter
  // (mirrors the design's visibleGroups(); works even if the backend
  // ignores the q param on /api/issues)
  const ql = q.toLowerCase();
  const visibleIssues = issues.filter(g =>
    (showResolved || g.status !== 'resolved') &&
    (!ql || g.exc.toLowerCase().includes(ql) || g.msg.toLowerCase().includes(ql) || g.service.includes(ql))
  );

  // Live badge counts for the sidebar
  const activeIssueCount = issues.filter(g => g.status !== 'resolved').length;
  const alertCount = (alertsData?.alerts || []).length;

  // Row menu items
  const menuIssue = issues.find(x => x.fp === menuFp);
  const rowMenuItems = menuIssue ? [
    {
      label: 'View details', color: 'var(--fg1,#d4d4d8)',
      onClick: () => { setMenuFp(null); setSheetFp(menuIssue.fp); },
    },
    menuIssue.status === 'resolved'
      ? {
          label: 'Reopen issue', color: 'var(--fg1,#d4d4d8)',
          onClick: () => { setMenuFp(null); handleReopen(menuIssue.fp); },
        }
      : {
          label: 'Resolve issue', color: 'var(--fg1,#d4d4d8)',
          onClick: () => { setMenuFp(null); handleResolve(menuIssue.fp); },
        },
    {
      label: 'Copy fingerprint', color: 'var(--fg1,#d4d4d8)',
      onClick: () => {
        setMenuFp(null);
        navigator.clipboard.writeText(menuIssue.fp).catch(() => {});
        notify('Fingerprint copied to clipboard.');
      },
    },
    menuIssue.github
      ? {
          label: `Open GitHub issue #${menuIssue.github.n} ↗`, color: '#93c5fd',
          onClick: () => { setMenuFp(null); window.open(menuIssue.github.url, '_blank'); },
        }
      : {
          label: 'Create GitHub issue', color: 'var(--fg1,#d4d4d8)',
          onClick: () => { setMenuFp(null); handleGithub(menuIssue.fp); },
        },
  ] : [];

  // Actions
  async function handleResolve(fp) {
    // Optimistic
    setIssues(prev => prev.map(x => x.fp === fp ? { ...x, status: 'resolved' } : x));
    if (sheetFp === fp) setSheetFp(null);
    try {
      const res = await resolveIssue(fp);
      notify(res.github_closed ? 'Resolved and closed GitHub issue.' : "Resolved. You'll be alerted immediately if it comes back.");
    } catch {
      notify("Can't reach Beacon server");
      loadAll(); // revert
    }
  }

  async function handleReopen(fp) {
    setIssues(prev => prev.map(x => x.fp === fp ? { ...x, status: 'active' } : x));
    setSheetIssue(prev => prev && prev.fp === fp ? { ...prev, status: 'active' } : prev);
    try {
      await reopenIssue(fp);
      notify('Issue reopened — back in the active list.');
    } catch {
      notify("Can't reach Beacon server");
      loadAll();
    }
  }

  async function handleGithub(fp) {
    const issue = issues.find(x => x.fp === fp);
    if (issue?.github) {
      window.open(issue.github.url, '_blank');
      return;
    }
    try {
      const res = await createGithubIssue(fp);
      if (res.ok) {
        setIssues(prev => prev.map(x => x.fp === fp ? { ...x, github: res.github } : x));
        if (sheetFp === fp) {
          setSheetIssue(prev => prev ? { ...prev, github: res.github } : prev);
        }
        notify(`GitHub issue #${res.github.n} created.`);
      } else {
        notify('Set GITHUB_TOKEN and GITHUB_REPO to enable GitHub issues.');
      }
    } catch {
      notify("Can't reach Beacon server");
    }
  }

  const sheetIssueObj = sheetIssue || issues.find(x => x.fp === sheetFp) || null;

  return (
    <div style={{
      fontFamily: "'Geist',system-ui,sans-serif",
      height: '100vh', display: 'flex',
      background: 'var(--bg,#09090b)', color: 'var(--fg,#fafafa)',
      fontSize: 14, overflow: 'hidden',
    }}>
      <Sidebar
        page={page}
        collapsed={sidebarCollapsed}
        onNavigate={handleNavigate}
        onToggle={() => setSidebarCollapsed(v => !v)}
        meta={meta}
        envFilter={envFilter}
        onEnvFilter={setEnvFilter}
        activeIssueCount={activeIssueCount}
        alertCount={alertCount}
      />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <Header
          page={page}
          q={q}
          onSearch={setQ}
          envFilter={envFilter}
          onEnvFilter={setEnvFilter}
          showResolved={showResolved}
          onToggleResolved={() => setShowResolved(v => !v)}
          alerts={alertsData?.alerts}
          issues={issues}
          onNavigate={handleNavigate}
        />

        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', minHeight: 0 }}>
          {page === 'issues' && (
            <>
              <StatCards page="issues" overview={overview} />
              <IssuesTable
                issues={visibleIssues}
                sheetFp={sheetFp}
                onOpenSheet={fp => setSheetFp(fp)}
                onMenu={(e, fp) => {
                  e.stopPropagation();
                  setMenuFp(prev => prev === fp ? null : fp);
                  setMenuPos({ x: e.clientX, y: e.clientY });
                }}
                rowPad={ROW_PAD}
              />
              <IssuesExtras
                alerts={alertsData}
                deploys={deploysData}
                meta={meta}
              />
            </>
          )}

          {page === 'llm' && (
            <LlmPage data={llmData} envFilter={envFilter} rowPad={ROW_PAD} />
          )}

          {page === 'alerts' && (
            <AlertsPage data={alertsData} rowPad={ROW_PAD} onNavigate={handleNavigate} />
          )}

          {page === 'deploys' && (
            <DeploysPage data={deploysData} rowPad={ROW_PAD} onNavigate={handleNavigate} />
          )}
        </div>
      </div>

      {/* Issue sheet */}
      {sheetFp && sheetIssueObj && (
        <IssueSheet
          issue={sheetIssueObj}
          onClose={() => setSheetFp(null)}
          onResolve={() => handleResolve(sheetFp)}
          onReopen={() => handleReopen(sheetFp)}
          onGithub={() => handleGithub(sheetFp)}
        />
      )}

      {/* Row context menu (click-away/Esc handled by App's document listeners) */}
      {menuFp && menuIssue && (
        <RowMenu items={rowMenuItems} pos={menuPos} />
      )}

      <Toast message={toast} />
    </div>
  );
}
