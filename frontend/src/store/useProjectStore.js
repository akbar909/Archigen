import { create } from 'zustand'
import { toast } from 'react-hot-toast'
import { layoutConflictSummary } from '../utils/layoutDiagnostics.js'
import { waitForModel } from '../utils/modelGeneration.js'
import { reconcileDraftDesign } from '../utils/draftReconciliation.js'
import {
  approveFloorPlan as apiApproveFloorPlan,
  createVersionBranch as apiCreateVersionBranch,
  createProject as apiCreateProject,
  deleteProject as apiDeleteProject,
  fetchLayoutValidation as apiFetchLayoutValidation,
  fetchProject as apiFetchProject,
  fetchProjects as apiFetchProjects,
  fetchVersion as apiFetchVersion,
  fetchVersions as apiFetchVersions,
  generate3D as apiGenerate3D,
  generateDesign as apiGenerateDesign,
  generateVersion as apiGenerateVersion,
  getApiErrorMessage,
  getGenerationErrorMessage,
  renameProject as apiRenameProject,
  updateLayout as apiUpdateLayout,
} from '../services'

const cloneJson = (value) => {
  if (value === null || value === undefined) return value
  if (typeof structuredClone === 'function') return structuredClone(value)
  return JSON.parse(JSON.stringify(value))
}

let modelPollToken = 0

export const useProjectStore = create((set, get) => ({
  // Data State
  projects: [],
  design: null,
  persistedDesign: null,
  activeProjectId: null,
  activeVersionId: null,

  // UI State
  loading: false,
  isVersionLoading: false,
  isGenerating3D: false,
  generation3D: null,
  isReloading3D: false,
  isApprovingLayout: false,
  isSavingVersion: false,
  isDirty: false,
  layoutValidation: null,
  sidebarLoading: false,
  projectAction: { type: null, projectId: null },
  sidebarOpen: false,
  sidebarCollapsed: false,
  activeTab: 'viewer', // 'viewer' | 'json'

  // Multi-floor & View Layers
  showRoof: true,
  activeFloorLevel: null,
  cutawayHeight: null,

  // Setters for UI
  setActiveTab: (tab) => set({ activeTab: tab }),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  toggleSidebarCollapsed: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setShowRoof: (showRoof) => set({ showRoof }),
  toggleShowRoof: () => set((state) => ({ showRoof: !state.showRoof })),
  setActiveFloorLevel: (activeFloorLevel) => set({ activeFloorLevel }),
  setCutawayHeight: (cutawayHeight) => set({ cutawayHeight }),
  setDraftDesign: (nextDesign) => set((state) => {
    const resolved = typeof nextDesign === 'function'
      ? nextDesign(cloneJson(state.design))
      : nextDesign
    return { ...reconcileDraftDesign(state.design, resolved, state.persistedDesign), layoutValidation: null }
  }),
  discardDraftChanges: () => set((state) => ({
    design: cloneJson(state.persistedDesign),
    isDirty: false,
  })),

  // Actions
  loadProjectsList: async ({ showLoader = true } = {}) => {
    if (showLoader) set({ sidebarLoading: true })
    try {
      const data = await apiFetchProjects()
      const projectsWithVersions = await Promise.all(
        (data.projects || []).map(async (project) => {
          try {
            const vData = await apiFetchVersions(project.id)
            return { ...project, versions: vData.versions || [] }
          } catch {
            return { ...project, versions: [] }
          }
        })
      )
      set({ projects: projectsWithVersions })
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to load projects'))
    } finally {
      if (showLoader) set({ sidebarLoading: false })
    }
  },

  selectVersion: async (projectId, versionId) => {
    if (get().projectAction?.type === 'deleting') {
      return null
    }

    // Keep an already usable version instant, but refresh an approved version
    // whose background Blender URL was not available during the previous read.
    const currentDesign = get().design
    if (
      get().activeProjectId === projectId &&
      get().activeVersionId === versionId &&
      currentDesign &&
      (!currentDesign.layout_approved || currentDesign.glb_url)
    ) {
      return currentDesign
    }

    ++modelPollToken
    set({
      activeProjectId: projectId,
      activeVersionId: versionId,
      design: null, // Loading indicator in viewport
      persistedDesign: null,
      isDirty: false,
      isVersionLoading: true,
      isGenerating3D: false,
      generation3D: null,
      activeTab: 'viewer',
    })
    try {
      const data = await apiFetchVersion(versionId)
      const ver = data.version
      const designData = ver?.design
        ? { ...ver.design, glb_url: ver.glb_url || ver.design.glb_url }
        : null
      set({
        design: designData,
        persistedDesign: cloneJson(designData),
        isDirty: false,
        isVersionLoading: false,
        generation3D: ver?.generation_3d || null,
        isGenerating3D: false,
      })

      // If version is approved but has no 3D glb model yet, poll in case it is finishing in background
      if (designData && (ver?.generation_3d?.status === 'running' || (!ver?.generation_3d && !designData.glb_url && designData.layout_approved))) {
        get().pollForGlbModel(versionId)
      }
      return data.version
    } catch (err) {
      set({ activeVersionId: null, design: null, persistedDesign: null, isDirty: false, isVersionLoading: false })
      if (get().projectAction?.type !== 'deleting') {
        if (err?.response?.status === 404) {
          toast.error('Design version not found')
        } else {
          toast.error(getApiErrorMessage(err, 'Failed to load design version'))
        }
      }
      return null
    }
  },

  selectProject: async (projectId) => {
    set({ activeProjectId: projectId, activeTab: 'viewer' })
    const { projects, selectVersion } = get()
    let project = projects.find((p) => p.id === projectId)

    if (!project) {
      try {
        const pData = await apiFetchProject(projectId)
        if (pData?.project) {
          project = { ...pData.project, versions: pData.versions || [] }
          set((state) => ({
            projects: state.projects.some((p) => p.id === projectId)
              ? state.projects
              : [project, ...state.projects],
          }))
        }
      } catch {
        // Handled below
      }
    }

    const latestVersion = project?.versions?.[0] || null
    if (latestVersion?.id) {
      await selectVersion(projectId, latestVersion.id)
      return { project, version: latestVersion }
    } else {
      set({ activeVersionId: null, design: null, persistedDesign: null, isDirty: false })
      return { project, version: null }
    }
  },

  createProject: async (projectName) => {
    const { projects, loadProjectsList } = get()
    const defaultName = `New Project ${projects.length + 1}`
    const raw = projectName !== undefined && projectName !== null
      ? projectName
      : window.prompt('Enter Project Name (2 - 30 characters)', defaultName)
    if (raw === null) return null
    const name = (raw || '').trim()

    if (!name || name.length < 2) {
      toast.error('Project name must be at least 2 characters')
      return null
    }
    if (name.length > 30) {
      toast.error('Project name cannot exceed 30 characters')
      return null
    }

    set({ loading: true })
    try {
      const data = await apiCreateProject({ name })
      if (data.success) {
        set({
          design: null,
          persistedDesign: null,
          isDirty: false,
          activeProjectId: data.project.id,
          activeVersionId: null,
          sidebarCollapsed: false,
          sidebarOpen: false,
        })
        toast.success('New project created. Describe your space to generate Version 1!')
        await loadProjectsList({ showLoader: false })
        return data.project
      }
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to create project'))
    } finally {
      set({ loading: false, sidebarOpen: false })
    }
    return null
  },

  createNewVersion: async (projectId) => {
    const { projects } = get()
    set({ activeProjectId: projectId, activeTab: 'viewer' })

    const targetProject = projects.find((p) => p.id === projectId)
    const latestVersion = targetProject?.versions?.[0] || null

    if (latestVersion?.id) {
      set({ activeVersionId: latestVersion.id, design: null, persistedDesign: null, isDirty: false })
      try {
        const data = await apiFetchVersion(latestVersion.id)
        set({
          design: data.version.design,
          persistedDesign: cloneJson(data.version.design),
          isDirty: false,
        })
      } catch (err) {
        toast.error(getApiErrorMessage(err, 'Failed to load project context'))
      }
    } else {
      set({ activeVersionId: null, design: null, persistedDesign: null, isDirty: false })
    }

    const input = document.getElementById('design-prompt-input')
    if (input) {
      input.focus()
      toast('Tell AI what to change for the next version', { icon: '✍️' })
    }
  },

  renameProject: async (projectId, newName) => {
    const trimmed = (newName || '').trim()
    if (!trimmed || trimmed.length < 2) {
      toast.error('Project name must be at least 2 characters')
      return
    }
    if (trimmed.length > 30) {
      toast.error('Project name cannot exceed 30 characters')
      return
    }

    set({ projectAction: { type: 'renaming', projectId } })
    try {
      await apiRenameProject(projectId, trimmed)
      await get().loadProjectsList({ showLoader: false })
      toast.success('Project renamed')
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to rename project'))
    } finally {
      set({ projectAction: { type: null, projectId: null } })
    }
  },

  deleteProject: async (projectId) => {
    if (!window.confirm('Are you sure? This will delete all versions of this project.')) {
      return { success: false, cancelled: true }
    }

    set({ projectAction: { type: 'deleting', projectId } })
    try {
      await apiDeleteProject(projectId)
      const wasActive = get().activeProjectId === projectId
      if (wasActive) {
        set({
          design: null,
          persistedDesign: null,
          isDirty: false,
          activeProjectId: null,
          activeVersionId: null,
        })
      }
      await get().loadProjectsList({ showLoader: false })
      toast.success('Project deleted')
      return { success: true, wasActive }
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to delete project'))
      return { success: false }
    } finally {
      set({ projectAction: { type: null, projectId: null } })
    }
  },

  generate: async ({ prompt, style, timeout = 120, wizard }) => {
    if (get().isDirty) {
      toast.error('Save or discard your draft changes before generating a new version')
      return null
    }
    const { activeProjectId, activeVersionId, loadProjectsList } = get()
    set({ loading: true })

    try {
      let data
      let resultProjectId = activeProjectId
      let resultVersionId = null

      if (activeProjectId) {
        data = await apiGenerateVersion(activeProjectId, {
          prompt,
          style,
          timeout,
          wizard,
          base_version_id: activeVersionId || undefined,
        })
        resultVersionId = data.version.id
        const designData = data.version.design
          ? { ...data.version.design, glb_url: data.version.glb_url || data.version.design.glb_url }
          : null
        set({
          design: designData,
          persistedDesign: cloneJson(designData),
          isDirty: false,
          activeVersionId: data.version.id,
        })
        toast.success(`Version ${data.version.version_num} generated! ✨`)
      } else {
        data = await apiGenerateDesign({ prompt, style, timeout, wizard })
        resultProjectId = data.project_id
        resultVersionId = data.design_id
        const designData = data.design
          ? { ...data.design, glb_url: data.glb_url || data.design.glb_url }
          : null
        set({
          design: designData,
          persistedDesign: cloneJson(designData),
          isDirty: false,
          activeProjectId: data.project_id,
          activeVersionId: data.design_id,
        })
        toast.success('Project created and design generated! ✨')
      }

      await loadProjectsList({ showLoader: false })

      // 3D synthesis will start once user approves 2D layout in CAD viewer
      return { projectId: resultProjectId, versionId: resultVersionId }
    } catch (err) {
      toast.error(getGenerationErrorMessage(err))
      return null
    } finally {
      set({ loading: false })
    }
  },

  pollForGlbModel: async (versionId, maxAttempts = 300, intervalMs = 2500) => {
    if (!versionId) return null
    const token = ++modelPollToken
    set({ isGenerating3D: true })
    const isCurrent = () => token === modelPollToken && get().activeVersionId === versionId
    const result = await waitForModel({
      fetchVersion: () => apiFetchVersion(versionId), isCurrent, maxAttempts, intervalMs,
      onStatus: generation3D => set({ generation3D }),
    })
    if (!isCurrent()) return null
    set({ isGenerating3D: false })
    if (result.status === 'completed') {
      set(state => {
        const nextDesign = { ...(state.design || result.version.design), glb_url: result.url }
        return { design: nextDesign, persistedDesign: state.isDirty ? state.persistedDesign : cloneJson(nextDesign) }
      })
      toast.success('3D model ready.', { id: 'model-generation' })
      await get().loadProjectsList({ showLoader: false })
      return result.url
    }
    if (result.status === 'waiting') toast(result.error, { id: 'model-generation', duration: 7000 })
    else if (result.status !== 'cancelled') toast.error(result.error, { id: 'model-generation', duration: 7000 })
    return null
  },

  regenerate3D: async (projectId, versionId) => {
    if (get().isDirty) {
      toast.error('Save your draft before synthesizing a new 3D model')
      return null
    }
    const pId = projectId || get().activeProjectId
    const vId = versionId || get().activeVersionId
    if (!pId || !vId) {
      toast.error('Cannot generate 3D: No active project/version')
      return null
    }

    set({ isGenerating3D: true })
    try {
      const data = await apiGenerate3D(pId, vId, { force: true })
      if (get().activeVersionId !== vId) return null
      if (data.success && data.pending) {
        set({ generation3D: data.version?.generation_3d || null })
        toast(data.already_running ? 'This 3D build is already running.' : '3D build started.', { id: 'model-generation' })
        return await get().pollForGlbModel(vId)
      } else if (data.success && data.glb_url) {
        set((state) => {
          const nextDesign = state.design ? { ...state.design, glb_url: data.glb_url } : state.design
          return { design: nextDesign, persistedDesign: cloneJson(nextDesign) }
        })
        toast.success('Blender 3D model generated successfully! ✨')
        await get().loadProjectsList({ showLoader: false })
        return data.glb_url
      } else {
        toast.error(data.error || 'Failed to generate 3D model')
      }
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to generate Blender 3D model'))
    } finally {
      if (get().activeVersionId === vId) set({ isGenerating3D: false })
    }
    return null
  },

  reloadSaved3D: async (versionId) => {
    const vId = versionId || get().activeVersionId
    if (!vId) {
      toast.error('Cannot reload 3D: No active design version')
      return null
    }

    set({ isReloading3D: true })
    try {
      // A plain version read only refreshes the temporary cloud URL. It never
      // runs Blender or replaces the already generated model.
      const data = await apiFetchVersion(vId)
      const version = data?.version
      const glbUrl = version?.glb_url || version?.design?.glb_url
      if (!glbUrl) {
        toast.error('No saved 3D model is available for this version')
        return null
      }
      set((state) => {
        const nextDesign = state.design
          ? { ...state.design, glb_url: glbUrl }
          : (version.design ? { ...version.design, glb_url: glbUrl } : null)
        return {
          design: nextDesign,
          persistedDesign: state.isDirty ? state.persistedDesign : cloneJson(nextDesign),
        }
      })
      return glbUrl
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to reload the saved 3D model'))
      return null
    } finally {
      set({ isReloading3D: false })
    }
  },

  approveFloorPlan: async (projectId, versionId) => {
    if (get().isDirty) {
      toast.error('Save your draft changes before approving the floor plan')
      return null
    }
    const pId = projectId || get().activeProjectId
    const vId = versionId || get().activeVersionId
    if (!pId || !vId) {
      toast.error('Cannot approve floor plan: No active project/version')
      return null
    }

    set({ isApprovingLayout: true })
    try {
      const data = await apiApproveFloorPlan(pId, vId)
      if (get().activeVersionId !== vId) return null
      if (data.success) {
        toast.success('3D build started.', { id: 'model-generation' })
        set((state) => {
          const nextDesign = data.version?.design
            ? { ...data.version.design, glb_url: data.version.glb_url || data.version.design.glb_url }
            : (state.design ? { ...state.design, layout_approved: true } : state.design)
          return {
          isApprovingLayout: false,
          isGenerating3D: true,
          generation3D: data.version?.generation_3d || null,
          design: nextDesign,
          persistedDesign: cloneJson(nextDesign),
          }
        })
        // Poll for Blender GLB model completion
        get().pollForGlbModel(vId)
        return data
      } else {
        toast.error(data.error || 'Failed to approve floor plan')
      }
    } catch (err) {
      const report = err?.response?.data?.validation
      if (report?.critical_errors?.length) {
        set({ layoutValidation: { versionId: vId, report } })
        toast.error(layoutConflictSummary(report.critical_errors.length), { id: 'layout-conflicts', duration: 4500 })
      } else toast.error('Could not approve this layout. Please try again.')
    } finally {
      set({ isApprovingLayout: false })
    }
    return null
  },

  updateLayout: async (projectId, versionId, layoutData) => {
    const pId = projectId || get().activeProjectId
    const vId = versionId || get().activeVersionId
    if (!pId || !vId) return null
    try {
      const data = await apiUpdateLayout(pId, vId, layoutData)
      if (data.success && data.design) {
        set({ design: data.design, persistedDesign: cloneJson(data.design), isDirty: false })
        toast.success('Layout updated successfully!')
        return data.design
      }
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to update layout'))
    }
    return null
  },

  saveLayoutChanges: async ({ mode = 'overwrite', note = '' } = {}) => {
    const {
      activeProjectId: projectId,
      activeVersionId: versionId,
      design,
      isSavingVersion,
      loadProjectsList,
    } = get()
    if (isSavingVersion) return null
    if (!projectId || !versionId || !design) {
      toast.error('Cannot save: No active design version')
      return null
    }
    if (!['overwrite', 'new_version'].includes(mode)) {
      toast.error('Unknown save mode')
      return null
    }

    set({ isSavingVersion: true })
    try {
      const trimmedNote = String(note || '').trim()
      const data = mode === 'new_version'
        ? await apiCreateVersionBranch(projectId, {
            base_version_id: versionId,
            design,
            note: trimmedNote,
          })
        : await apiUpdateLayout(projectId, versionId, design, { note: trimmedNote })

      const version = data?.version
      const savedDesign = data?.design || version?.design
      const nextVersionId = version?.id || versionId
      if (!data?.success || !savedDesign) {
        throw new Error('The server did not return the saved design')
      }
      const report = data.validation
      const hasConflicts = Boolean(report?.critical_errors?.length)

      const previewGlbUrl = version?.glb_url || savedDesign.glb_url || design.glb_url || design.model_url
      const resolvedDesign = previewGlbUrl
        ? { ...savedDesign, glb_url: previewGlbUrl }
        : savedDesign
      set({
        design: resolvedDesign,
        persistedDesign: cloneJson(resolvedDesign),
        // Dashboard navigates to a new branch after this action resolves. Keep
        // the current route/store IDs aligned until that navigation occurs.
        activeVersionId: mode === 'new_version' ? versionId : nextVersionId,
        isDirty: false,
        layoutValidation: hasConflicts ? { versionId: nextVersionId, report } : null,
      })
      await loadProjectsList({ showLoader: false })
      toast.success(
        mode === 'new_version'
          ? `Saved as Version ${version?.version_num}`
          : `Version ${version?.version_num || ''} saved`.trim(),
      )
      return { ...data, design: resolvedDesign, mode, versionId: nextVersionId, rebuilt3D: false }
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to save design changes'))
      return null
    } finally {
      set({ isSavingVersion: false })
    }
  },

  fetchValidation: async (projectId, versionId) => {
    const pId = projectId || get().activeProjectId
    const vId = versionId || get().activeVersionId
    if (!pId || !vId) return null
    try {
      const data = await apiFetchLayoutValidation(pId, vId)
      return data
    } catch (err) {
      console.warn('Failed to fetch validation:', err)
      return null
    }
  },

  reset: () => {
    ++modelPollToken
    set({
      projects: [],
      design: null,
      persistedDesign: null,
      activeProjectId: null,
      activeVersionId: null,
      loading: false,
      isGenerating3D: false,
      generation3D: null,
      isApprovingLayout: false,
      isSavingVersion: false,
      isDirty: false,
      showRoof: true,
      activeFloorLevel: null,
      cutawayHeight: null,
      sidebarLoading: false,
      projectAction: { type: null, projectId: null },
      sidebarOpen: false,
      activeTab: 'viewer',
    })
  },
}))
