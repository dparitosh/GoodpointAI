import React, { useMemo } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { E2ETraceBreadcrumbs } from '../components/e2etrace-breadcrumbs';
import WorkflowProgress from '../components/WorkflowProgress';
import { useE2ETraceTheme } from '../contexts/e2etrace-theme-context.jsx';
import { useTranslation } from 'react-i18next';
import goodPointLogo from '../assets/goodpoint-logo.svg';
import './e2etrace-root-layout.css';

const NAV_GROUPS = [
  {
    id: 'overview',
    titleKey: 'nav.overview',
    href: '/',
    matchPrefixes: ['/'],
    items: [
      { to: '/', labelKey: 'nav.overview', end: true },
    ],
  },
  {
    id: 'workflows',
    titleKey: 'nav.dataProcessingHub',
    href: '/processing',
    matchPrefixes: ['/processing', '/workflow', '/workflow-manager'],
    items: [
      { to: '/processing', labelKey: 'nav.dataProcessingHub' },
    ],
  },
  {
    id: 'migration',
    titleKey: 'nav.migrationTools',
    href: '/data-config',
    matchPrefixes: ['/data-config', '/spreadsheet', '/lineage'],
    items: [
      { to: '/data-config', labelKey: 'nav.dataConfig' },
      { to: '/spreadsheet', labelKey: 'nav.spreadsheet' },
      { to: '/lineage', labelKey: 'nav.dataLineage' },
    ],
  },
  {
    id: 'insights',
    titleKey: 'nav.insightsReports',
    href: '/reporting',
    matchPrefixes: ['/self-healing', '/observability', '/analytics', '/reporting'],
    items: [
      { to: '/reporting', labelKey: 'nav.reporting' },
      { to: '/analytics', labelKey: 'nav.analytics' },
      { to: '/observability', labelKey: 'nav.observability' },
      { to: '/self-healing', labelKey: 'nav.selfHealingMonitor' },
    ],
  },
  {
    id: 'advanced',
    titleKey: 'nav.advancedTools',
    href: '/graph-explorer',
    matchPrefixes: ['/graph-explorer', '/graphexplorer', '/multimodal', '/api-docs'],
    items: [
      { to: '/graph-explorer', labelKey: 'nav.graphExplorer' },
      { to: '/multimodal', labelKey: 'nav.multiModalAnalyzer' },
      { to: '/api-docs', labelKey: 'nav.apiDocs' },
    ],
  },
  {
    id: 'settings',
    titleKey: 'nav.settings',
    href: '/settings',
    matchPrefixes: ['/settings'],
    items: [{ to: '/settings', labelKey: 'nav.preferences' }],
  },
];

export const E2ETraceRootLayout = () => {
  const location = useLocation();
  const { theme, toggleTheme } = useE2ETraceTheme();
  const { t } = useTranslation();

  // Some pages (like the Landing hero) are designed to be full-bleed and should
  // not be wrapped in the standard padded card.
  const isFullBleedPage = location.pathname === '/';

  const activeNavGroup = useMemo(() => {
    const pathname = location.pathname || '/';

    // Special-case exact home.
    if (pathname === '/') {
      return NAV_GROUPS.find((g) => g.id === 'overview') ?? NAV_GROUPS[0];
    }

    const match = NAV_GROUPS.find((group) =>
      group.matchPrefixes.some((prefix) => {
        if (prefix === '/') return false;
        return pathname === prefix || pathname.startsWith(prefix + '/');
      }),
    );

    return match ?? NAV_GROUPS[0];
  }, [location.pathname]);
  
  return (
    <div className="e2etrace-app-container">
      <header className="e2etrace-app-header">
        <div className="e2etrace-header-top">
          <div className="e2etrace-app-logo">
            <img src={goodPointLogo} alt="GoodPoint" className="goodpoint-logo-img" />
            <div className="e2etrace-branding">
              <span className="e2etrace-title">GoodPoint AgenticAI</span>
              <span className="e2etrace-subtitle">PLM Data Migration Platform</span>
            </div>
          </div>

          <div className="e2etrace-header-actions">
            <div className="e2etrace-header-workflow-progress" aria-label="Workflow progress">
              <WorkflowProgress
                currentPage={location.pathname}
                showDetails={false}
                showNavigation={false}
              />
            </div>
            <button
              type="button"
              className="e2etrace-theme-toggle"
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
            </button>
          </div>
        </div>

        <nav className="e2etrace-header-nav" aria-label="Primary navigation">
          <div className="e2etrace-primary-tabs" aria-label="Main sections">
            {NAV_GROUPS.map((group) => {
              const isActive = group.id === activeNavGroup.id;
              return (
                <NavLink
                  key={group.id}
                  to={group.href}
                  className={`e2etrace-primary-tab ${isActive ? 'active' : ''}`}
                  aria-current={isActive ? 'page' : undefined}
                >
                  {t(group.titleKey)}
                </NavLink>
              );
            })}
          </div>

          <div className="e2etrace-secondary-tabs" aria-label="Sub sections">
            {activeNavGroup.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `e2etrace-secondary-tab ${isActive ? 'active' : ''}`
                }
              >
                {t(item.labelKey)}
              </NavLink>
            ))}
          </div>
        </nav>
      </header>

      <div className="e2etrace-main-content-wrapper">
        <div className={`e2etrace-content-area ${isFullBleedPage ? 'full-bleed' : ''}`}>
          {!isFullBleedPage ? (
            <>
              <E2ETraceBreadcrumbs />
            </>
          ) : null}
          <main className={isFullBleedPage ? 'e2etrace-page-content-full' : 'e2etrace-page-content'}>
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
};