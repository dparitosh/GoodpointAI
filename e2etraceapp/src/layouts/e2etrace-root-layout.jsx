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
    icon: 'fas fa-home',
    href: '/',
    matchPrefixes: ['/'],
    items: [
      { to: '/', labelKey: 'nav.overview', icon: 'fas fa-home', end: true },
    ],
  },
  {
    id: 'search',
    titleKey: 'nav.search',
    icon: 'fas fa-comments',
    href: '/search',
    matchPrefixes: ['/search'],
    items: [
      { to: '/search', labelKey: 'nav.conversationalSearch', icon: 'fas fa-comments' },
    ],
  },
  {
    id: 'migration',
    titleKey: 'nav.migration',
    icon: 'fas fa-exchange-alt',
    href: '/migration',
    matchPrefixes: ['/migration'],
    items: [
      { to: '/migration', labelKey: 'nav.migrationWizard', icon: 'fas fa-magic' },
    ],
  },
  {
    id: 'workflows',
    titleKey: 'nav.ruleEngine',
    icon: 'fas fa-clipboard-check',
    href: '/rule-engine',
    matchPrefixes: ['/rule-engine', '/workflow'],
    items: [
      { to: '/rule-engine', labelKey: 'nav.ruleEngine', icon: 'fas fa-clipboard-check' },
    ],
  },
  {
    id: 'insights',
    titleKey: 'nav.insightsReports',
    icon: 'fas fa-chart-bar',
    href: '/analytics',
    matchPrefixes: ['/lineage', '/self-healing', '/observability', '/analytics', '/dq-dashboard', '/data-discovery', '/reporting-hub'],
    items: [
      { to: '/lineage', labelKey: 'nav.dataLineage', icon: 'fas fa-stream' },
      { to: '/analytics', labelKey: 'nav.analytics', icon: 'fas fa-chart-line' },
      { to: '/dq-dashboard', labelKey: 'nav.dqDashboard', icon: 'fas fa-shield-alt' },
      { to: '/data-discovery', labelKey: 'nav.dataDiscovery', icon: 'fas fa-search-location' },
      { to: '/observability', labelKey: 'nav.observability', icon: 'fas fa-eye' },
      { to: '/self-healing', labelKey: 'nav.selfHealingMonitor', icon: 'fas fa-heartbeat' },
      { to: '/reporting-hub', labelKey: 'nav.reportingHub', icon: 'fas fa-clipboard-list' },
    ],
  },
  {
    id: 'advanced',
    titleKey: 'nav.advancedTools',
    icon: 'fas fa-toolbox',
    href: '/graph-explorer',
    matchPrefixes: ['/graph-explorer', '/multimodal', '/batch-processor', '/api-docs'],
    items: [
      { to: '/graph-explorer', labelKey: 'nav.graphExplorer', icon: 'fas fa-project-diagram' },
      { to: '/multimodal', labelKey: 'nav.multiModalAnalyzer', icon: 'fas fa-brain' },
      { to: '/batch-processor', labelKey: 'nav.batchProcessor', icon: 'fas fa-layer-group' },
      { to: '/api-docs', labelKey: 'nav.apiDocs', icon: 'fas fa-book' },
    ],
  },
  {
    id: 'settings',
    titleKey: 'nav.settings',
    icon: 'fas fa-cog',
    href: '/settings',
    matchPrefixes: ['/settings', '/admin'],
    items: [
      { to: '/settings', labelKey: 'nav.preferences', icon: 'fas fa-sliders-h' },
      { to: '/admin', labelKey: 'nav.adminSettings', icon: 'fas fa-user-cog' },
    ],
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
              <i className={theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon'} aria-hidden="true" />
              <span>{theme === 'dark' ? 'Light' : 'Dark'}</span>
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
                  <i className={group.icon} aria-hidden="true" />
                  <span>{t(group.titleKey)}</span>
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
                <i className={item.icon} aria-hidden="true" />
                <span>{t(item.labelKey)}</span>
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