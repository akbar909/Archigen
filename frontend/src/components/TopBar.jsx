import { useProjectStore } from '../store'

const SidebarToggleIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M9 4v16" />
  </svg>
)

const BuildingIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="4" y="2" width="16" height="20" rx="2" />
    <path d="M9 22V12h6v10M9 7h1M14 7h1M9 11h1M14 11h1" />
  </svg>
)

const JsonIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
    <polyline points="10 9 9 9 8 9" />
  </svg>
)

export default function TopBar() {
  const {
    projects,
    activeProjectId,
    activeVersionId,
    design,
    activeTab,
    setActiveTab,
    sidebarCollapsed,
    setSidebarCollapsed,
    setSidebarOpen,
  } = useProjectStore()

  const activeProject = projects.find((p) => p.id === activeProjectId)
  const activeVersion = activeProject?.versions?.find((v) => v.id === activeVersionId)
  const activeVersionNum = activeVersion ? activeVersion.version_num : null

  return (
    <div className="topbar">
      <div className="topbar-left">
        {sidebarCollapsed && (
          <button
            className="menu-toggle desktop-only"
            onClick={() => setSidebarCollapsed(false)}
            aria-label="Open sidebar"
            title="Open sidebar"
          >
            <SidebarToggleIcon />
          </button>
        )}
        <button
          className="menu-toggle mobile-only"
          onClick={() => setSidebarOpen(true)}
          aria-label="Toggle sidebar"
          title="Toggle sidebar"
        >
          <SidebarToggleIcon />
        </button>
        <div>
          <div className="topbar-title">
            {activeProject ? activeProject.name : 'ArchiGen'}
            {activeVersionNum ? (
              <span
                style={{
                  marginLeft: 10,
                  fontSize: '0.7rem',
                  verticalAlign: 'middle',
                  background: 'var(--accent-glow)',
                  color: 'var(--accent)',
                  border: '1px solid rgba(16,163,127,0.3)',
                  borderRadius: 4,
                  padding: '2px 6px',
                }}
              >
                Version {activeVersionNum}
              </span>
            ) : null}
          </div>
          <div className="topbar-sub">
            {activeProject ? 'Working on project' : 'AI 3D Home Architect'}
          </div>
        </div>
      </div>

      <div className="topbar-right">
        {design && (
          <div
            style={{
              display: 'flex',
              gap: 4,
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              padding: 3,
            }}
          >
            {[
              { id: 'viewer', label: '3D View', icon: <BuildingIcon /> },
              { id: 'json', label: 'JSON', icon: <JsonIcon /> },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 5,
                  padding: '5px 12px',
                  border: 'none',
                  borderRadius: 4,
                  cursor: 'pointer',
                  fontSize: '0.8125rem',
                  fontWeight: 500,
                  fontFamily: 'inherit',
                  background: activeTab === tab.id ? 'var(--bg-tertiary)' : 'transparent',
                  color: activeTab === tab.id ? 'var(--text-primary)' : 'var(--text-muted)',
                  transition: 'all 0.15s',
                }}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>
        )}

        <div className="live-badge">
          <div className="live-dot" />
          Live
        </div>
      </div>
    </div>
  )
}
