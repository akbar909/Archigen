/* eslint-disable react/prop-types */
import { useState } from 'react'
import { toast } from 'react-hot-toast'
import { CheckCircle2, Download, Loader2, Save, Sparkles } from 'lucide-react'
import { useProjectStore } from '../store'
import { getCachedModelUrl } from '../utils/modelCache'

const SidebarToggleIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M9 4v16" />
  </svg>
)

const ShareLinkIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
  </svg>
)

export default function TopBar({ onOpenWizard, onOpenSave }) {
  const {
    projects,
    activeProjectId,
    activeVersionId,
    design,
    sidebarCollapsed,
    setSidebarCollapsed,
    setSidebarOpen,
    isDirty,
    isSavingVersion,
  } = useProjectStore()

  const activeProject = projects.find((p) => p.id === activeProjectId)
  const activeVersion = activeProject?.versions?.find((v) => v.id === activeVersionId)
  const activeVersionNum = activeVersion ? activeVersion.version_num : null

  const [isDownloading, setIsDownloading] = useState(false)
  const glbUrl = design?.glb_url || design?.model_url || null

  const handleCopyLink = () => {
    try {
      navigator.clipboard.writeText(window.location.href)
      toast.success('Page link copied to clipboard! 📋')
    } catch {
      toast.error('Failed to copy link')
    }
  }

  const handleDownload3D = async () => {
    if (!glbUrl) {
      toast.error('No 3D model available yet. Generate or approve layout first.')
      return
    }

    setIsDownloading(true)
    const toastId = toast.loading('Preparing 3D model download…')

    try {
      let blob = null
      const cachedBlobUrl = await getCachedModelUrl(glbUrl)
      if (cachedBlobUrl) {
        const res = await fetch(cachedBlobUrl)
        blob = await res.blob()
      } else {
        const res = await fetch(glbUrl)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        blob = await res.blob()
      }

      const cleanProjectName = (activeProject?.name || 'House_Design').replace(/[^a-zA-Z0-9_-]/g, '_')
      const fileName = `${cleanProjectName}_v${activeVersionNum || 1}.glb`

      const blobUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = blobUrl
      link.download = fileName
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(blobUrl)

      toast.success('3D Model (.glb) downloaded! 🏡💾', { id: toastId })
    } catch (err) {
      console.warn('[TopBar] Blob download failed, attempting direct link download:', err)
      try {
        const cleanProjectName = (activeProject?.name || 'House_Design').replace(/[^a-zA-Z0-9_-]/g, '_')
        const link = document.createElement('a')
        link.href = glbUrl
        link.download = `${cleanProjectName}_v${activeVersionNum || 1}.glb`
        link.target = '_blank'
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        toast.success('3D Model download started! 🏡', { id: toastId })
      } catch {
        toast.error('Failed to download 3D model.', { id: toastId })
      }
    } finally {
      setIsDownloading(false)
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
        {design && (
          <button
            type="button"
            className={`version-save-trigger ${isDirty ? 'dirty' : 'saved'}`}
            onClick={onOpenSave}
            disabled={!isDirty || isSavingVersion}
            title={isDirty ? 'Save design changes' : 'All changes are saved'}
          >
            {isSavingVersion ? (
              <Loader2 size={14} className="animate-spin" />
            ) : isDirty ? (
              <Save size={14} />
            ) : (
              <CheckCircle2 size={14} />
            )}
            <span>{isSavingVersion ? 'Saving…' : isDirty ? 'Save changes' : 'Saved'}</span>
          </button>
        )}

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

        {/* 3D Model Download Button */}
        {design && (
          <button
            type="button"
            onClick={handleDownload3D}
            disabled={!glbUrl || isDownloading}
            title={glbUrl ? 'Download 3D Model (.glb)' : '3D Model not synthesized yet'}
            aria-label="Download 3D Model"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 12px',
              background: glbUrl ? 'rgba(16, 163, 127, 0.12)' : 'var(--bg-secondary)',
              border: `1px solid ${glbUrl ? 'rgba(16, 163, 127, 0.35)' : 'var(--border)'}`,
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.8125rem',
              fontWeight: 600,
              color: glbUrl ? '#10a37f' : 'var(--text-muted)',
              cursor: glbUrl && !isDownloading ? 'pointer' : 'not-allowed',
              opacity: glbUrl ? 1 : 0.6,
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              if (glbUrl && !isDownloading) {
                e.currentTarget.style.background = 'rgba(16, 163, 127, 0.22)'
                e.currentTarget.style.borderColor = '#10a37f'
              }
            }}
            onMouseLeave={(e) => {
              if (glbUrl && !isDownloading) {
                e.currentTarget.style.background = 'rgba(16, 163, 127, 0.12)'
                e.currentTarget.style.borderColor = 'rgba(16, 163, 127, 0.35)'
              }
            }}
          >
            {isDownloading ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Download size={14} />
            )}
            <span>{isDownloading ? 'Downloading…' : '3D Model'}</span>
          </button>
        )}

        {!design && onOpenWizard && (
          <button
            type="button"
            onClick={onOpenWizard}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/25 hover:border-emerald-500/50 transition-all cursor-pointer shadow-sm"
            title="Design a new house with the multi-step wizard"
          >
            <Sparkles size={13} />
            <span className="hidden sm:inline">Design</span> Wizard
          </button>
        )}

        <div className="live-badge">
          <div className="live-dot" />
          Live
        </div>
      </div>
    </div>
  )
}
