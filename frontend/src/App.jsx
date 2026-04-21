import { useEffect, useMemo, useState } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { Toaster, toast } from 'react-hot-toast'
import './App.css'
import AuthPanel from './components/AuthPanel'
import Sidebar from './components/Sidebar'
import ChatInput from './components/ChatInput'
import Viewer3D from './components/Viewer3D'
import LandingPage from './components/LandingPage'
import { 
  fetchDesign, 
  fetchHistory, 
  generateDesign, 
  login, 
  register,
  fetchProjects,
  createProject,
  generateVersion,
  fetchVersion,
  fetchVersions
} from './services/api'

// ──────────────────────────────────────────
// Icon helpers
// ──────────────────────────────────────────
const MenuIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 12h18M3 6h18M3 18h18" />
  </svg>
)

const BuildingIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="4" y="2" width="16" height="20" rx="2" /><path d="M9 22V12h6v10M9 7h1M14 7h1M9 11h1M14 11h1" />
  </svg>
)

const JsonIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
  </svg>
)

// ──────────────────────────────────────────
// Main App
// ──────────────────────────────────────────
function App() {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('archigen_user')
    if (!stored || stored === 'undefined') return null
    try { return JSON.parse(stored) } catch { return null }
  })

  // Data State
  const [projects, setProjects] = useState([])
  const [design, setDesign] = useState(null)
  
  // Tracking state
  const [activeProjectId, setActiveProjectId] = useState(null)
  const [activeVersionId, setActiveVersionId] = useState(null)
  
  // UI State
  const [loading, setLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('viewer') // 'viewer' | 'json'
  
  const navigate = useNavigate()
  const isAuthed = !!user

  const storeSession = (data) => {
    localStorage.setItem('archigen_token', data.token)
    const userData = data.user || { token: data.token }
    localStorage.setItem('archigen_user', JSON.stringify(userData))
    setUser(userData)
  }

  const clearSession = () => {
    localStorage.removeItem('archigen_token')
    localStorage.removeItem('archigen_user')
    setUser(null)
    setDesign(null)
    setProjects([])
    setActiveProjectId(null)
    setActiveVersionId(null)
    toast.success('Signed out successfully')
    navigate('/auth')
  }

  const loadProjectsList = async () => {
    try {
      const data = await fetchProjects()
      // For each project, fetch its versions to populate the sidebar list
      const projectsWithVersions = await Promise.all(
        (data.projects || []).map(async (project) => {
          const vData = await fetchVersions(project.id)
          return { ...project, versions: vData.versions || [] }
        })
      )
      setProjects(projectsWithVersions)
    } catch (err) {
      toast.error(err?.response?.data?.error || 'Failed to load projects')
    }
  }

  useEffect(() => {
    if (isAuthed) loadProjectsList()
  }, [isAuthed])

  const handleAuth = async (mode, payload) => {
    try {
      const fn = mode === 'register' ? register : login
      const data = await fn(payload)
      storeSession(data)
      toast.success(mode === 'register' ? 'Account created! Welcome to ArchiGen 🎉' : 'Welcome back! 👋')
      await loadProjectsList()
      navigate('/app')
    } catch (err) {
      const detail = err?.response?.data?.error || err.message || 'Authentication failed'
      toast.error(detail)
    }
  }

  const handleSend = async ({ prompt, style }) => {
    setLoading(true)
    try {
      let data;
      if (activeProjectId) {
        // Generate new version in existing project
        data = await generateVersion(activeProjectId, { prompt, style })
        setDesign(data.version.design)
        setActiveVersionId(data.version.id)
        toast.success(`Version ${data.version.version_num} generated! ✨`)
      } else {
        // Generate new standalone (Legacy fallback/Auto-project)
        data = await generateDesign({ prompt, style })
        setDesign(data.design)
        toast.success('Project created and design generated! ✨')
        setActiveProjectId(data.project_id)
        setActiveVersionId(data.design_id)
      }
      
      await loadProjectsList()
    } catch (err) {
      const detail = err?.response?.data?.error || err.message || 'Generation failed'
      toast.error(detail)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectVersion = async (projectId, versionId) => {
    setActiveProjectId(projectId)
    setActiveVersionId(versionId)
    setDesign(null) // Show loading state
    try {
      const data = await fetchVersion(versionId)
      setDesign(data.version.design)
      setActiveTab('viewer')
    } catch (err) {
      toast.error(err?.response?.data?.error || 'Failed to load design version')
    }
  }

  const handleNewProject = async () => {
    const name = window.prompt("Enter Project Name", `New Project ${projects.length + 1}`)
    if (!name) return

    setLoading(true)
    try {
      const data = await createProject({ name })
      if (data.success) {
        setDesign(null)
        setActiveProjectId(data.project.id)
        setActiveVersionId(null)
        toast.success('New project created. Describe your space to generate Version 1!')
        await loadProjectsList()
      }
    } catch (err) {
      toast.error('Failed to create project')
    } finally {
      setLoading(false)
      setSidebarOpen(false)
    }
  }

  const handleNewVersion = (projectId, style) => {
    setActiveProjectId(projectId)
    // We don't clear the version yet, just focus the input
    const input = document.getElementById('design-prompt-input')
    if (input) {
      input.focus()
      toast('Tell AI what to change for the next version', { icon: '✍️' })
    }
  }

  const handleRenameProject = async (projectId, newName) => {
    try {
      await renameProject(projectId, newName)
      await loadProjectsList()
      toast.success('Project renamed')
    } catch (err) {
      toast.error('Failed to rename')
    }
  }

  const handleDeleteProject = async (projectId) => {
    if (!window.confirm("Are you sure? This will delete all versions of this project.")) return
    try {
      await deleteProject(projectId)
      if (activeProjectId === projectId) {
        setDesign(null)
        setActiveProjectId(null)
        setActiveVersionId(null)
      }
      await loadProjectsList()
      toast.success('Project deleted')
    } catch (err) {
      toast.error('Failed to delete')
    }
  }

  const summary = useMemo(() => {
    if (!design) return null
    const rooms = Array.isArray(design.rooms) ? design.rooms.length : 0
    const doors = Array.isArray(design.doors) ? design.doors.length : 0
    const windows = Array.isArray(design.windows) ? design.windows.length : 0
    return { rooms, doors, windows }
  }, [design])

  const activeProject = useMemo(() => {
    return projects.find(p => p.id === activeProjectId)
  }, [projects, activeProjectId])

  const activeVersionNum = useMemo(() => {
    if (!activeProject || !activeVersionId) return null
    const v = activeProject.versions.find(v => v.id === activeVersionId)
    return v ? v.version_num : null
  }, [activeProject, activeVersionId])

  // ── App Shell View (after login) ──────────────────
  const renderAppView = () => (
    <div className="app-shell">
      {/* Sidebar */}
      <Sidebar
        projects={projects}
        activeProjectId={activeProjectId}
        activeVersionId={activeVersionId}
        onSelectVersion={handleSelectVersion}
        onNewVersion={handleNewVersion}
        onNewProject={handleNewProject}
        onRenameProject={handleRenameProject}
        onDeleteProject={handleDeleteProject}
        user={user}
        onLogout={clearSession}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main area */}
      <div className="main-area">
        {/* TopBar */}
        <div className="topbar">
          <div className="topbar-left">
            {/* Hamburger — mobile only */}
            <button
              className="menu-toggle mobile-only"
              onClick={() => setSidebarOpen(v => !v)}
              aria-label="Toggle sidebar"
            >
              <MenuIcon />
            </button>
            <div>
              <div className="topbar-title">
                {activeProject ? activeProject.name : 'ArchiGen'}
                {activeVersionNum ? (
                  <span style={{ 
                    marginLeft: 10, fontSize: '0.7rem', verticalAlign: 'middle',
                    background: 'var(--accent-glow)', color: 'var(--accent)',
                    border: '1px solid rgba(16,163,127,0.3)', borderRadius: 4, padding: '2px 6px'
                  }}>
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
            {/* Tabs */}
            {design && (
              <div style={{ display: 'flex', gap: 4, background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: 3 }}>
                {[
                  { id: 'viewer', label: '3D View', icon: <BuildingIcon /> },
                  { id: 'json', label: 'JSON', icon: <JsonIcon /> },
                ].map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 5,
                      padding: '5px 12px', border: 'none', borderRadius: 4, cursor: 'pointer',
                      fontSize: '0.8125rem', fontWeight: 500, fontFamily: 'inherit',
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

        {/* Content Area */}
        <div className="content-area">
          {!design && !loading && (
            // Empty state
            <div className="empty-state">
              <div className="empty-state-icon">🏗️</div>
              <div className="empty-state-title">
                {activeProject ? `Project: ${activeProject.name}` : 'Design your dream space'}
              </div>
              <div className="empty-state-sub">
                {activeProject 
                  ? 'Ready to generate Version 1. Describe your space below to begin.' 
                  : 'Select a project or create a new one to start designing architectural layouts.'}
              </div>

              {/* Stats summary */}
              {!activeProject && projects.length > 0 && (
                <div style={{ display: 'flex', gap: 12, marginTop: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
                  <div className="stat-card" style={{ minWidth: 'unset', padding: '10px 16px', textAlign: 'center' }}>
                    <div className="stat-value stat-accent">{projects.length}</div>
                    <div className="stat-label">Projects Managed</div>
                  </div>
                </div>
              )}
            </div>
          )}

          {loading && (
            <div className="empty-state">
              <div style={{ fontSize: '2.5rem', animation: 'pulse-dot 1.5s ease-in-out infinite' }}>⚡</div>
              <div className="empty-state-title">Generating your design…</div>
              <div className="empty-state-sub">AI is sculpting your space. This usually takes under 10 seconds.</div>
              {/* Loading skeleton */}
              <div style={{ width: '100%', maxWidth: 600, marginTop: 24, display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[100, 80, 65].map(w => (
                  <div key={w} style={{
                    height: 14, borderRadius: 7, width: `${w}%`,
                    background: 'var(--bg-secondary)',
                    animation: 'pulse-dot 1.5s ease-in-out infinite',
                  }} />
                ))}
              </div>
            </div>
          )}

          {design && (
            <>
              {/* Design summary stats */}
              {summary && (
                <div className="stats-row fade-up">
                  <div className="stat-card">
                    <div className="stat-label">Rooms</div>
                    <div className="stat-value stat-accent">{summary.rooms}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Doors</div>
                    <div className="stat-value">{summary.doors}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Windows</div>
                    <div className="stat-value">{summary.windows}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Style</div>
                    <div className="stat-value" style={{ fontSize: '0.875rem', textTransform: 'capitalize' }}>
                      {design?.style || design?.metadata?.style || '—'}
                    </div>
                  </div>
                </div>
              )}

              {/* Tab content */}
              {activeTab === 'viewer' && (
                <div className="viewer-card fade-up" style={{ flex: 1, minHeight: 420 }}>
                  <div className="viewer-card-header">
                    <div>
                      <div className="viewer-card-title">3D Visualization</div>
                      <div className="viewer-card-sub">Drag to rotate · Scroll to zoom · Right-click to pan</div>
                    </div>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#60a5fa' }} />
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#34d399' }} />
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#fbbf24' }} />
                    </div>
                  </div>
                  <Viewer3D design={design} />
                </div>
              )}

              {activeTab === 'json' && (
                <div className="json-card fade-up">
                  <div className="json-card-header">
                    <div>
                      <div className="viewer-card-title">Design JSON Output</div>
                      <div className="viewer-card-sub">Structured layout data · Ready for downstream tools</div>
                    </div>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(JSON.stringify(design, null, 2))
                        toast.success('Copied to clipboard!')
                      }}
                      style={{
                        background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
                        color: 'var(--text-secondary)', borderRadius: 'var(--radius-sm)',
                        padding: '5px 12px', fontSize: '0.75rem', cursor: 'pointer', fontFamily: 'inherit'
                      }}
                    >
                      Copy JSON
                    </button>
                  </div>
                  <pre className="json-body scroll-soft">
                    {JSON.stringify(design, null, 2)}
                  </pre>
                </div>
              )}
            </>
          )}

          {/* Spacer for input */}
          <div style={{ height: 8 }} />
        </div>

        {/* Fixed Bottom Input */}
        <ChatInput
          onSend={handleSend}
          loading={loading}
          disabled={false}
        />
      </div>
    </div>
  )

  return (
    <>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'var(--bg-secondary)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.875rem',
            fontFamily: 'Inter, sans-serif',
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
          },
          success: { iconTheme: { primary: '#10a37f', secondary: 'white' } },
          error: { iconTheme: { primary: '#ef4444', secondary: 'white' } },
        }}
      />
      <Routes>
        {/* Landing page — always accessible */}
        <Route path="/" element={<LandingPage />} />

        {/* Auth — redirects to /app if already logged in */}
        <Route
          path="/auth"
          element={isAuthed ? <Navigate to="/app" /> : <AuthPanel onAuth={handleAuth} />}
        />

        {/* Main app — requires auth */}
        <Route
          path="/app"
          element={isAuthed ? renderAppView() : <Navigate to="/auth" />}
        />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to={isAuthed ? '/app' : '/'} />} />
      </Routes>
    </>
  )
}

export default App
