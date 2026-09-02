import { useState } from 'react'
import { useAuthStore, useProjectStore } from '../store'

// ── Icons ──────────────────────────────────────────────────────────
const PlusIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 5v14M5 12h14" />
  </svg>
)
const LogoutIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" />
  </svg>
)
const PanelToggleIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M9 4v16" />
  </svg>
)
const FolderIcon = ({ open }) => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
  </svg>
)
const ChevronIcon = ({ open }) => (
  <svg
    width="12"
    height="12"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    style={{ transform: open ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}
  >
    <path d="M9 18l6-6-6-6" />
  </svg>
)
const EditIcon = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
  </svg>
)
const TrashIcon = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 6h18M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6M10 11v6M14 11v6M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2" />
  </svg>
)
const SpinnerIcon = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="sidebar-spin">
    <path d="M21 12a9 9 0 11-6.2-8.56" />
  </svg>
)

// ── Version badge colours by number ──────────────────────────────────
function versionColor(n) {
  const colors = ['#10a37f', '#2563eb', '#7c3aed', '#d97706', '#dc2626']
  return colors[(n - 1) % colors.length]
}

// ── Single project row (expandable) ──────────────────────────────────
function ProjectRow({
  project,
  activeProjectId,
  activeVersionId,
  onSelectVersion,
  onNewVersion,
  onRename,
  onDelete,
  expandedId,
  setExpandedId,
  actionType,
  actionProjectId,
}) {
  const isExpanded = expandedId === project.id
  const isActive = activeProjectId === project.id

  const versions = project.versions || []
  const vCount = project.version_count || versions.length || 1
  const isRenaming = actionType === 'renaming' && actionProjectId === project.id
  const isDeleting = actionType === 'deleting' && actionProjectId === project.id
  const actionBusy = isRenaming || isDeleting

  const toggle = (e) => {
    e.stopPropagation()
    setExpandedId(isExpanded ? null : project.id)
  }

  const handleRename = async (e) => {
    e.stopPropagation()
    const nextName = window.prompt('Rename project', project.name)
    if (!nextName) return
    const trimmed = nextName.trim()
    if (!trimmed || trimmed === project.name) return
    await onRename(project.id, trimmed)
  }

  const handleDelete = async (e) => {
    e.stopPropagation()
    await onDelete(project.id)
  }

  return (
    <div>
      {/* Project header row */}
      <div
        className={`sidebar-item ${isActive ? 'active' : ''}`}
        style={{ padding: '7px 8px', cursor: 'pointer' }}
        onClick={toggle}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
          <span style={{ flexShrink: 0, color: 'var(--text-muted)' }}>
            <ChevronIcon open={isExpanded} />
          </span>

          <span style={{ flexShrink: 0, color: isActive ? 'var(--accent)' : 'var(--text-muted)' }}>
            <FolderIcon open={isExpanded} />
          </span>

          <span className="sidebar-item-title" style={{ flex: 1 }}>
            {project.name}
          </span>

          <span
            style={{
              flexShrink: 0,
              fontSize: '0.6rem',
              fontWeight: 700,
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border)',
              color: 'var(--text-muted)',
              borderRadius: 4,
              padding: '1px 5px',
            }}
          >
            v{vCount}
          </span>
        </div>

        {/* Style badge */}
        <div className="sidebar-item-meta" style={{ paddingLeft: 32, marginTop: 2 }}>
          <span className="sidebar-item-badge">{project.style || 'modern'}</span>
          <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
            {project.updated_at ? new Date(project.updated_at).toLocaleDateString() : ''}
          </span>

          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}>
            <button
              type="button"
              onClick={handleRename}
              title="Rename project"
              aria-label="Rename project"
              disabled={actionBusy}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 20,
                height: 20,
                background: 'transparent',
                border: '1px solid var(--border)',
                borderRadius: 4,
                color: 'var(--text-muted)',
                cursor: actionBusy ? 'not-allowed' : 'pointer',
                opacity: actionBusy && !isRenaming ? 0.5 : 1,
              }}
            >
              {isRenaming ? <SpinnerIcon /> : <EditIcon />}
            </button>

            <button
              type="button"
              onClick={handleDelete}
              title="Delete project"
              aria-label="Delete project"
              disabled={actionBusy}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 20,
                height: 20,
                background: 'transparent',
                border: '1px solid var(--border)',
                borderRadius: 4,
                color: 'var(--danger)',
                cursor: actionBusy ? 'not-allowed' : 'pointer',
                opacity: actionBusy && !isDeleting ? 0.5 : 1,
              }}
            >
              {isDeleting ? <SpinnerIcon /> : <TrashIcon />}
            </button>
          </div>
        </div>
      </div>

      {/* Expanded: versions list */}
      {isExpanded && (
        <div style={{ paddingLeft: 20, paddingBottom: 4 }}>
          {versions.map((v) => (
            <div
              key={v.id}
              onClick={() => onSelectVersion(project.id, v.id, v.version_num)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                padding: '5px 8px',
                borderRadius: 5,
                cursor: 'pointer',
                border: `1px solid ${activeVersionId === v.id ? 'var(--border-hover)' : 'transparent'}`,
                background: activeVersionId === v.id ? 'var(--bg-tertiary)' : 'transparent',
                transition: 'all 0.12s',
                marginBottom: 2,
              }}
              onMouseEnter={(e) => {
                if (activeVersionId !== v.id) e.currentTarget.style.background = 'var(--bg-tertiary)'
              }}
              onMouseLeave={(e) => {
                if (activeVersionId !== v.id) e.currentTarget.style.background = 'transparent'
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  flexShrink: 0,
                  background: versionColor(v.version_num),
                }}
              />
              <span
                style={{
                  fontSize: '0.65rem',
                  fontWeight: 700,
                  color: versionColor(v.version_num),
                  flexShrink: 0,
                }}
              >
                v{v.version_num}
              </span>
              <span
                style={{
                  fontSize: '0.75rem',
                  color: 'var(--text-secondary)',
                  flex: 1,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {v.prompt || 'Untitled'}
              </span>
            </div>
          ))}

          <button
            onClick={(e) => {
              e.stopPropagation()
              onNewVersion(project.id, project.style)
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '5px 8px',
              width: '100%',
              background: 'transparent',
              border: '1px dashed var(--border)',
              borderRadius: 5,
              cursor: 'pointer',
              color: 'var(--text-muted)',
              fontSize: '0.75rem',
              marginTop: 4,
              transition: 'all 0.12s',
              fontFamily: 'inherit',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--accent)'
              e.currentTarget.style.color = 'var(--accent)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--border)'
              e.currentTarget.style.color = 'var(--text-muted)'
            }}
          >
            <PlusIcon />
            Refine / New Version
          </button>
        </div>
      )}
    </div>
  )
}

// ── Main Sidebar ──────────────────────────────────────────────────────
export default function Sidebar(props) {
  const store = useProjectStore()
  const authStore = useAuthStore()

  const projects = props.projects ?? store.projects
  const activeProjectId = props.activeProjectId ?? store.activeProjectId
  const activeVersionId = props.activeVersionId ?? store.activeVersionId
  const isOpen = props.isOpen ?? store.sidebarOpen
  const isCollapsed = props.isCollapsed ?? store.sidebarCollapsed
  const loading = props.loading ?? store.sidebarLoading
  const actionType = props.actionType ?? store.projectAction.type
  const actionProjectId = props.actionProjectId ?? store.projectAction.projectId
  const user = props.user ?? authStore.user

  const onSelectVersion = props.onSelectVersion ?? store.selectVersion
  const onNewVersion = props.onNewVersion ?? store.createNewVersion
  const onNewProject = props.onNewProject ?? (() => store.createProject())
  const onRenameProject = props.onRenameProject ?? store.renameProject
  const onDeleteProject = props.onDeleteProject ?? store.deleteProject
  const onLogout = props.onLogout ?? authStore.logout
  const onClose = props.onClose ?? (() => store.setSidebarOpen(false))
  const onToggleCollapse = props.onToggleCollapse ?? store.toggleSidebarCollapsed

  const [expandedId, setExpandedId] = useState(activeProjectId || null)
  const [search, setSearch] = useState('')

  const filtered = projects.filter(
    (p) => !search || p.name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <>
      {/* Mobile overlay */}
      <div className={`sidebar-overlay ${isOpen ? 'active' : ''}`} onClick={onClose} />

      <aside className={`sidebar ${isOpen ? 'open' : ''} ${isCollapsed ? 'collapsed' : ''}`}>
        {/* Header */}
        <div className="sidebar-header">
          <div className="sidebar-logo">
            Archi<span>Gen</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button
              onClick={onToggleCollapse}
              className="menu-toggle desktop-only"
              title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              type="button"
            >
              <PanelToggleIcon />
            </button>
            <button
              onClick={onNewProject}
              className="menu-toggle"
              title="New Project"
              type="button"
            >
              <PlusIcon />
            </button>
          </div>
        </div>

        {/* New Project CTA */}
        <button onClick={onNewProject} className="sidebar-new-btn" type="button">
          <PlusIcon />
          <span>New Project</span>
        </button>

        {/* Search */}
        {projects.length > 2 && (
          <div style={{ padding: '0 2px 4px' }}>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search projects…"
              style={{
                width: '100%',
                padding: '7px 10px',
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-primary)',
                fontSize: '0.8125rem',
                outline: 'none',
                fontFamily: 'inherit',
              }}
            />
          </div>
        )}

        {/* Projects list */}
        <div className="sidebar-history scroll-soft" style={{ flex: 1 }}>
          {loading && (
            <div style={{ padding: '8px 4px 12px' }}>
              {Array.from({ length: 6 }).map((_, idx) => (
                <div key={idx} className="sidebar-skeleton-item">
                  <div className="sidebar-skeleton-row">
                    <span className="sidebar-skeleton-dot" />
                    <span className="sidebar-skeleton-line w-55" />
                    <span className="sidebar-skeleton-line w-15" />
                  </div>
                  <div className="sidebar-skeleton-row meta">
                    <span className="sidebar-skeleton-line w-22" />
                    <span className="sidebar-skeleton-line w-28" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {!loading && filtered.length === 0 && (
            <div style={{ padding: '32px 8px', textAlign: 'center' }}>
              <div style={{ fontSize: '1.75rem', marginBottom: 8 }}>🏗️</div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                {search ? 'No matching projects' : 'No projects yet'}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>
                {search ? 'Try a different search' : 'Click "New Project" to start designing'}
              </div>
            </div>
          )}

          {!loading &&
            filtered.map((project) => (
              <ProjectRow
                key={project.id}
                project={project}
                activeProjectId={activeProjectId}
                activeVersionId={activeVersionId}
                onSelectVersion={(pid, vid, vnum) => {
                  onSelectVersion(pid, vid, vnum)
                  if (onClose) onClose()
                }}
                onNewVersion={onNewVersion}
                onRename={onRenameProject}
                onDelete={onDeleteProject}
                expandedId={expandedId}
                setExpandedId={setExpandedId}
                actionType={actionType}
                actionProjectId={actionProjectId}
              />
            ))}
        </div>

        {/* Footer — user */}
        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="sidebar-avatar">
              {user?.name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'A'}
            </div>
            <div className="sidebar-user-info">
              <div className="sidebar-user-name">{user?.name || user?.email || 'Architect'}</div>
              <div className="sidebar-user-role">
                {projects.length} project{projects.length !== 1 ? 's' : ''}
              </div>
            </div>
            <button onClick={onLogout} className="sidebar-logout-btn" title="Sign out" type="button">
              <LogoutIcon />
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}
