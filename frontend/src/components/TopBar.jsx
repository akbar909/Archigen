import { toast } from 'react-hot-toast'
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

const ShareLinkIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
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

  const handleCopyLink = () => {
    try {
      navigator.clipboard.writeText(window.location.href)
      toast.success('Page link copied to clipboard! 📋')
    } catch {
      toast.error('Failed to copy link')
    }
  }

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
        {activeProjectId && (
          <button
            type="button"
            onClick={handleCopyLink}
            title="Copy page link to share or bookmark"
            aria-label="Copy page link"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 11px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-secondary)',
              fontSize: '0.8125rem',
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--accent)'
              e.currentTarget.style.color = 'var(--accent)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--border)'
              e.currentTarget.style.color = 'var(--text-secondary)'
            }}
          >
            <ShareLinkIcon />
            <span>Copy Link</span>
          </button>
        )}

        {/* 3D View mode badge */}
        {design && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              padding: '5px 12px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.8125rem',
              fontWeight: 500,
              color: 'var(--text-primary)',
            }}
          >
            <BuildingIcon />
            <span>3D Model</span>
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
