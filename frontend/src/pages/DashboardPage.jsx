import { useEffect, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import TopBar from '../components/TopBar'
import Viewer3D from '../components/Viewer3D'
import ChatInput from '../components/ChatInput'
import StatsRow from '../components/StatsRow'
import JsonViewer from '../components/JsonViewer'
import { useAuthStore, useProjectStore } from '../store'

export default function DashboardPage() {
  const { projectId, versionId } = useParams()
  const navigate = useNavigate()
  const { isAuthed } = useAuthStore()
  const {
    projects,
    activeProjectId,
    activeVersionId,
    design,
    loading,
    activeTab,
    loadProjectsList,
    selectProject,
    selectVersion,
    generate,
  } = useProjectStore()

  useEffect(() => {
    if (isAuthed) {
      loadProjectsList()
    }
  }, [isAuthed, loadProjectsList])

  // Sync route parameters with project store
  useEffect(() => {
    if (!isAuthed) return

    const { projectAction } = useProjectStore.getState()
    if (projectAction?.type === 'deleting') return

    if (projectId && versionId) {
      if (activeProjectId !== projectId || activeVersionId !== versionId) {
        selectVersion(projectId, versionId).then((res) => {
          if (!res) {
            navigate(projectId ? `/app/projects/${projectId}` : '/app', { replace: true })
          }
        })
      }
    } else if (projectId) {
      if (activeProjectId !== projectId) {
        selectProject(projectId).then((res) => {
          if (res?.version?.id) {
            navigate(`/app/projects/${projectId}/versions/${res.version.id}`, { replace: true })
          } else if (!res?.project) {
            navigate('/app', { replace: true })
          }
        })
      }
    } else if (!projectId && !versionId && activeProjectId) {
      // User navigated to /app root
      useProjectStore.setState({ activeProjectId: null, activeVersionId: null, design: null })
    }
  }, [projectId, versionId, isAuthed, activeProjectId, activeVersionId, selectProject, selectVersion, navigate])

  const activeProject = useMemo(() => {
    return projects.find((p) => p.id === activeProjectId)
  }, [projects, activeProjectId])

  const hasGeneratedAnyDesign = useMemo(() => {
    if (design) return true
    return projects.some((project) => Array.isArray(project.versions) && project.versions.length > 0)
  }, [design, projects])

  const handleGenerate = async (params) => {
    const result = await generate(params)
    if (result?.projectId && result?.versionId) {
      navigate(`/app/projects/${result.projectId}/versions/${result.versionId}`)
    }
  }

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <Sidebar />

      {/* Main area */}
      <div className="main-area">
        {/* TopBar */}
        <TopBar />

        {/* Content Area */}
        <div className="content-area">
          {!design && !loading && (
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
              <div className="empty-state-title">Generating your architectural layout…</div>
              <div className="empty-state-sub">Assembling rooms, multi-part furniture, and realistic lighting.</div>
              {/* Loading skeleton */}
              <div style={{ width: '100%', maxWidth: 600, marginTop: 24, display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[100, 80, 65].map((w) => (
                  <div
                    key={w}
                    style={{
                      height: 14,
                      borderRadius: 7,
                      width: `${w}%`,
                      background: 'var(--bg-secondary)',
                      animation: 'pulse-dot 1.5s ease-in-out infinite',
                    }}
                  />
                ))}
              </div>
            </div>
          )}

          {design && (
            <div className="viewer-stage-container fade-up" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, height: '100%', overflow: 'hidden' }}>
              {activeTab === 'json' && (
                <div style={{ marginBottom: 6, flexShrink: 0 }}>
                  <StatsRow design={design} />
                </div>
              )}

              {/* Tab content */}
              {activeTab === 'viewer' && (
                <div className="viewer-stage" style={{ flex: 1, minHeight: 0, height: '100%', width: '100%', position: 'relative', overflow: 'hidden' }}>
                  <Viewer3D design={design} />
                </div>
              )}

              {activeTab === 'json' && <JsonViewer design={design} />}
            </div>
          )}
        </div>

        {/* Fixed Bottom Input */}
        <ChatInput
          onSend={handleGenerate}
          loading={loading}
          disabled={false}
          showQuickPrompts={!hasGeneratedAnyDesign}
        />
      </div>
    </div>
  )
}
