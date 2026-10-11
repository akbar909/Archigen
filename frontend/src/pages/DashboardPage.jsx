import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import TopBar from '../components/TopBar'
import Viewer3D from '../components/Viewer3D'
import ChatInput from '../components/ChatInput'
import StatsRow from '../components/StatsRow'
import JsonViewer from '../components/JsonViewer'
import HomeWizard from '../components/home-wizard/HomeWizard'
import { useAuthStore, useProjectStore } from '../store'
import { Sparkles, MessageSquare } from 'lucide-react'

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

  // Track mode when no design is loaded (wizard vs prompt box)
  const [wizardActive, setWizardActive] = useState(true)
  // Track modal wizard when viewing an existing 3D design
  const [showWizardModal, setShowWizardModal] = useState(false)

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
    setShowWizardModal(false)
    const result = await generate(params)
    if (result?.projectId && result?.versionId) {
      navigate(`/app/projects/${result.projectId}/versions/${result.versionId}`)
    }
  }

  const handleOpenWizard = () => {
    if (!design) {
      setWizardActive(true)
    } else {
      setShowWizardModal(true)
    }
  }

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <Sidebar />

      {/* Main area */}
      <div className="main-area">
        {/* TopBar */}
        <TopBar onOpenWizard={handleOpenWizard} />

        {/* Content Area */}
        <div className="content-area" style={{ position: 'relative' }}>
          {/* No Design loaded & not loading */}
          {!design && !loading && (
            <>
              {wizardActive ? (
                <div className="flex flex-col flex-1 h-full min-h-0 w-full overflow-hidden">
                  <div className="flex-1 min-h-0 overflow-hidden">
                    <HomeWizard
                      onGenerate={handleGenerate}
                      loading={loading}
                      onSwitchToPrompt={() => setWizardActive(false)}
                    />
                  </div>
                </div>
              ) : (
                <div className="empty-state">
                  <div className="empty-state-icon">🏗️</div>
                  <div className="empty-state-title">
                    {activeProject ? `Project: ${activeProject.name}` : 'Design your dream space'}
                  </div>
                  <div className="empty-state-sub">
                    {activeProject
                      ? 'Ready to generate Version 1. Describe your space below or launch our guided wizard.'
                      : 'Select a project or create a new one to start designing architectural layouts.'}
                  </div>

                  <div className="mt-4 flex flex-wrap items-center justify-center gap-3">
                    <button
                      type="button"
                      onClick={() => setWizardActive(true)}
                      className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-emerald-600 to-emerald-500 text-white hover:from-emerald-500 hover:to-emerald-400 shadow-[0_0_20px_rgba(16,163,127,0.3)] transition-all cursor-pointer"
                    >
                      <Sparkles size={16} />
                      <span>Start Guided Design Wizard</span>
                    </button>
                  </div>

                  {/* Stats summary */}
                  {!activeProject && projects.length > 0 && (
                    <div style={{ display: 'flex', gap: 12, marginTop: 24, flexWrap: 'wrap', justifyContent: 'center' }}>
                      <div className="stat-card" style={{ minWidth: 'unset', padding: '10px 16px', textAlign: 'center' }}>
                        <div className="stat-value stat-accent">{projects.length}</div>
                        <div className="stat-label">Projects Managed</div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {/* Loading State */}
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

          {/* Loaded Design (3D Viewer / JSON) */}
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

        {/* Fixed Bottom Input: Only shown when a design is loaded OR when in quick prompt mode */}
        {(design || !wizardActive) && (
          <ChatInput
            onSend={handleGenerate}
            onOpenWizard={handleOpenWizard}
            loading={loading}
            disabled={false}
            showQuickPrompts={!hasGeneratedAnyDesign}
          />
        )}
      </div>

      {/* Modal Wizard for generating a new design while viewing an existing 3D model */}
      {showWizardModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-2 sm:p-6 animate-fadeIn">
          <div className="relative w-full max-w-5xl h-full max-h-[92vh] bg-[#0d0d0d] border border-white/10 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
            <HomeWizard
              onGenerate={handleGenerate}
              loading={loading}
              onClose={() => setShowWizardModal(false)}
            />
          </div>
        </div>
      )}
    </div>
  )
}
