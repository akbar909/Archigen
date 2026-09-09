import { create } from 'zustand'
import { toast } from 'react-hot-toast'
import {
  createProject as apiCreateProject,
  deleteProject as apiDeleteProject,
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
} from '../services'

export const useProjectStore = create((set, get) => ({
  // Data State
  projects: [],
  design: null,
  activeProjectId: null,
  activeVersionId: null,

  // UI State
  loading: false,
  isGenerating3D: false,
  sidebarLoading: false,
  projectAction: { type: null, projectId: null },
  sidebarOpen: false,
  sidebarCollapsed: false,
  activeTab: 'viewer', // 'viewer' | 'json'

  // Setters for UI
  setActiveTab: (tab) => set({ activeTab: tab }),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  toggleSidebarCollapsed: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

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

    // If version is already loaded with design, skip refetching
    if (get().activeProjectId === projectId && get().activeVersionId === versionId && get().design) {
      return get().design
    }

    set({
      activeProjectId: projectId,
      activeVersionId: versionId,
      design: null, // Loading indicator in viewport
      activeTab: 'viewer',
    })
    try {
      const data = await apiFetchVersion(versionId)
      const ver = data.version
      const designData = ver?.design
        ? { ...ver.design, glb_url: ver.glb_url || ver.design.glb_url }
        : null
      set({ design: designData })

      // If version has no 3D glb model, poll briefly in case it is finishing in background
      if (designData && !designData.glb_url) {
        get().pollForGlbModel(versionId, 10, 3000)
      }
      return data.version
    } catch (err) {
      set({ activeVersionId: null, design: null })
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
      set({ activeVersionId: null, design: null })
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
      set({ activeVersionId: latestVersion.id, design: null })
      try {
        const data = await apiFetchVersion(latestVersion.id)
        set({ design: data.version.design })
      } catch (err) {
        toast.error(getApiErrorMessage(err, 'Failed to load project context'))
      }
    } else {
      set({ activeVersionId: null, design: null })
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

  generate: async ({ prompt, style }) => {
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
          base_version_id: activeVersionId || undefined,
        })
        resultVersionId = data.version.id
        const designData = data.version.design
          ? { ...data.version.design, glb_url: data.version.glb_url || data.version.design.glb_url }
          : null
        set({
          design: designData,
          activeVersionId: data.version.id,
        })
        toast.success(`Version ${data.version.version_num} generated! ✨`)
      } else {
        data = await apiGenerateDesign({ prompt, style })
        resultProjectId = data.project_id
        resultVersionId = data.design_id
        const designData = data.design
          ? { ...data.design, glb_url: data.glb_url || data.design.glb_url }
          : null
        set({
          design: designData,
          activeProjectId: data.project_id,
          activeVersionId: data.design_id,
        })
        toast.success('Project created and design generated! ✨')
      }

      await loadProjectsList({ showLoader: false })

      // Automatically poll for Cloud Blender 3D synthesis
      if (resultVersionId) {
        get().pollForGlbModel(resultVersionId)
      }

      return { projectId: resultProjectId, versionId: resultVersionId }
    } catch (err) {
      toast.error(getGenerationErrorMessage(err))
      return null
    } finally {
      set({ loading: false })
    }
  },

  pollForGlbModel: async (versionId, maxAttempts = 40, intervalMs = 2500) => {
    if (!versionId) return null
    set({ isGenerating3D: true })

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, intervalMs))

      // If user switched away from this version while polling, stop
      if (get().activeVersionId !== versionId) {
        set({ isGenerating3D: false })
        return null
      }

      try {
        const data = await apiFetchVersion(versionId)
        const glbUrl = data?.version?.glb_url || data?.version?.design?.glb_url
        if (glbUrl) {
          set((state) => ({
            design: state.design
              ? { ...state.design, glb_url: glbUrl }
              : (data.version.design ? { ...data.version.design, glb_url: glbUrl } : null),
            isGenerating3D: false,
          }))
          toast.success('Cloud Blender 3D Model ready! 🏡✨')
          await get().loadProjectsList({ showLoader: false })
          return glbUrl
        }
      } catch {
        // Silently continue polling
      }
    }

    set({ isGenerating3D: false })
    return null
  },

  regenerate3D: async (projectId, versionId) => {
    const pId = projectId || get().activeProjectId
    const vId = versionId || get().activeVersionId
    if (!pId || !vId) {
      toast.error('Cannot generate 3D: No active project/version')
      return null
    }

    set({ isGenerating3D: true })
    try {
      const data = await apiGenerate3D(pId, vId)
      if (data.success && data.glb_url) {
        set((state) => ({
          design: state.design ? { ...state.design, glb_url: data.glb_url } : state.design,
        }))
        toast.success('Blender 3D model generated successfully! ✨')
        await get().loadProjectsList({ showLoader: false })
        return data.glb_url
      } else {
        toast.error(data.error || 'Failed to generate 3D model')
      }
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to generate Blender 3D model'))
    } finally {
      set({ isGenerating3D: false })
    }
    return null
  },

  reset: () => {
    set({
      projects: [],
      design: null,
      activeProjectId: null,
      activeVersionId: null,
      loading: false,
      isGenerating3D: false,
      sidebarLoading: false,
      projectAction: { type: null, projectId: null },
      sidebarOpen: false,
      activeTab: 'viewer',
    })
  },
}))
