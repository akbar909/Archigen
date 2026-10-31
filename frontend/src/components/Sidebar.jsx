/* eslint-disable react/prop-types */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
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
const FolderIcon = () => (
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
    <path d="M11 4H4a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
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

function versionChangeTags(summary) {
  if (!summary || typeof summary !== 'object') return []
  const labels = {
    rooms: 'Room',
    walls: 'Wall',
    doors: 'Door',
    windows: 'Window',
    furniture: 'Furniture',
  }
  const tags = []
  Object.entries(labels).forEach(([key, label]) => {
    const change = summary[key] || {}
    if (change.added) tags.push(`+${change.added} ${label}`)
    if (change.removed) tags.push(`-${change.removed} ${label}`)
    if (change.modified) tags.push(`${change.modified} ${label} edited`)
  })
  return tags.slice(0, 2)
}

// ── Single project row (expandable) ──────────────────────────────────
function ProjectRow({
  project,
  activeProjectId,
  activeVersionId,
  onSelectProject,
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

  const handleRowClick = (e) => {
    e.stopPropagation()
    setExpandedId(project.id)
    if (onSelectProject) {
      onSelectProject(project.id)
    }
  }

  const handleRename = async (e) => {
    e.stopPropagation()
    const nextName = window.prompt('Rename project (2 - 30 characters)', project.name)
    if (nextName === null) return // User cancelled
    const trimmed = (nextName || '').trim()
    if (trimmed === project.name) return

    if (!trimmed || trimmed.length < 2) {
      toast.error('Project name must be at least 2 characters')
      return
    }
    if (trimmed.length > 30) {
      toast.error('Project name cannot exceed 30 characters')
      return
    }
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
        onClick={handleRowClick}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
          <span
            style={{ flexShrink: 0, color: 'var(--text-muted)', padding: '2px 4px' }}
            onClick={toggle}
            title={isExpanded ? 'Collapse versions' : 'Expand versions'}
          >
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

          <div className="sidebar-project-actions" style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}>
            <button
              type="button"
              onClick={handleRename}
              title="Rename project"
              aria-label="Rename project"
              className="sidebar-project-rename"
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
              className="sidebar-project-delete"
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
          {versions.map((v) => {
            const changeTags = versionChangeTags(v.change_summary)
            return (
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
              <div
                style={{
                  flex: 1,
                  minWidth: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 3,
                }}
              >
                <span
                  title={v.version_note || v.prompt || 'Untitled'}
                  style={{
                  fontSize: '0.75rem',
                  color: 'var(--text-secondary)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  }}
                >
                  {v.version_note || v.prompt || 'Untitled'}
                </span>
                {changeTags.length > 0 && (
                  <span style={{ display: 'flex', gap: 3, overflow: 'hidden' }}>
                    {changeTags.map((tag) => (
                      <span
                        key={tag}
                        style={{
                          padding: '1px 4px',
                          borderRadius: 3,
                          background: 'rgba(16, 163, 127, 0.1)',
                          color: 'var(--accent)',
                          fontSize: '0.55rem',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {tag}
                      </span>
                    ))}
                  </span>
                )}
              </div>
            </div>
            )
          })}

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
            New Version
          </button>
        </div>
      )}
    </div>
  )
}

export default function Sidebar(props) {
  const navigate = useNavigate()
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
  const isDirty = props.isDirty ?? store.isDirty
  const user = props.user ?? authStore.user
  const accountName = user?.name && user.name.trim().toLowerCase() !== user.email?.trim().toLowerCase()
    ? user.name : user?.email?.split('@')[0] || 'Architect'

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

  const handleSelectVersion = (pid, vid) => {
    if (
      isDirty
      && vid !== activeVersionId
      && !window.confirm('You have unsaved design changes. Discard them and switch versions?')
    ) return
    navigate(`/app/projects/${pid}/versions/${vid}`)
    if (onClose) onClose()
  }

  const handleSelectProject = (pid) => {
    if (
      isDirty
      && pid !== activeProjectId
      && !window.confirm('You have unsaved design changes. Discard them and switch projects?')
    ) return
    navigate(`/app/projects/${pid}`)
  }

  const handleNewProject = async () => {
    if (isDirty && !window.confirm('You have unsaved design changes. Discard them and create a project?')) return
    const project = await onNewProject()
    if (project?.id) {
      navigate(`/app/projects/${project.id}`)
    }
  }

  const handleDeleteProject = async (pid) => {
    const wasActive = activeProjectId === pid
    if (wasActive) {
      navigate('/app', { replace: true })
    }
    await onDeleteProject(pid)
  }

  return (
    <>
      {/* Mobile overlay */}
      <div className={`sidebar-overlay ${isOpen ? 'active' : ''}`} onClick={onClose} />

      <aside className={`sidebar ${isOpen ? 'open' : ''} ${isCollapsed ? 'collapsed' : ''}`}>
        {/* Header */}
        <div className="sidebar-header">
          <div className="sidebar-logo" onClick={() => navigate('/app')} style={{ cursor: 'pointer' }}>
            Archi<span>Gen</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button type="button" className="menu-toggle mobile-only" onClick={onClose} aria-label="Close navigation">✕</button>
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
              onClick={handleNewProject}
              className="menu-toggle"
              title="New Project"
              type="button"
            >
              <PlusIcon />
            </button>
          </div>
        </div>

        {/* New Project CTA */}
        <button onClick={handleNewProject} className="sidebar-new-btn" type="button">
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
                onSelectProject={handleSelectProject}
                onSelectVersion={handleSelectVersion}
                onNewVersion={(pid, style) => {
                  onNewVersion(pid, style)
                  navigate(`/app/projects/${pid}`)
                }}
                onRename={onRenameProject}
                onDelete={handleDeleteProject}
                expandedId={expandedId}
                setExpandedId={setExpandedId}
                actionType={actionType}
                actionProjectId={actionProjectId}
              />
            ))}
        </div>

        {/* Footer — user */}
        <div className="sidebar-footer lg:pt-2 lg:pb-1">
          <div className="sidebar-user lg:px-2 lg:py-2 lg:gap-2">
            <div className="sidebar-avatar lg:w-7 lg:h-7 lg:text-xs">
              {user?.name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'A'}
            </div>
            <div className="sidebar-user-info lg:min-w-0 lg:flex-1 lg:overflow-hidden">
              <div className="sidebar-user-name lg:truncate lg:text-[13px] lg:leading-tight" title={accountName}>{accountName}</div>
              {user?.email && (
                <div
                  className="sidebar-user-email lg:truncate lg:whitespace-nowrap lg:overflow-hidden lg:text-ellipsis lg:text-[11px] lg:leading-normal"
                  title={user.email}
                >
                  {user.email}
                </div>
              )}
              <div className="sidebar-user-role lg:text-[11px] lg:leading-tight">
                {projects.length} project{projects.length !== 1 ? 's' : ''}
              </div>
            </div>
            <button
              onClick={onLogout}
              className="sidebar-logout-btn lg:w-7 lg:h-7 lg:min-w-[28px] lg:min-h-[28px] lg:p-1 lg:hover:text-red-400"
              title="Sign out"
              aria-label="Sign out"
              type="button"
            >
              <LogoutIcon />
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}
