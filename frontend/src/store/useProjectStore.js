import { create } from 'zustand'
import { toast } from 'react-hot-toast'
import {
  createProject as apiCreateProject,
  deleteProject as apiDeleteProject,
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
    set({
      activeProjectId: projectId,
      activeVersionId: versionId,
      design: null, // Loading indicator in viewport
      activeTab: 'viewer',
    })
    try {
      const data = await apiFetchVersion(versionId)
      set({ design: data.version.design })
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to load design version'))
    }
  },

  createProject: async (projectName) => {
    const { projects, loadProjectsList } = get()
    const name = projectName || window.prompt('Enter Project Name', `New Project ${projects.length + 1}`)
    if (!name) return false

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
        return true
      }
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to create project'))
    } finally {
      set({ loading: false, sidebarOpen: false })
    }
    return false
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
    set({ projectAction: { type: 'renaming', projectId } })
    try {
      await apiRenameProject(projectId, newName)
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
      return
    }

    set({ projectAction: { type: 'deleting', projectId } })
    try {
      await apiDeleteProject(projectId)
      if (get().activeProjectId === projectId) {
        set({
          design: null,
          activeProjectId: null,
          activeVersionId: null,
        })
      }
      await get().loadProjectsList({ showLoader: false })
      toast.success('Project deleted')
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to delete project'))
    } finally {
      set({ projectAction: { type: null, projectId: null } })
    }
  },

  generate: async ({ prompt, style }) => {
    const { activeProjectId, activeVersionId, loadProjectsList } = get()
    set({ loading: true })

    try {
      let data
      if (activeProjectId) {
        data = await apiGenerateVersion(activeProjectId, {
          prompt,
          style,
          base_version_id: activeVersionId || undefined,
        })
        set({
          design: data.version.design,
          activeVersionId: data.version.id,
        })
        toast.success(`Version ${data.version.version_num} generated! ✨`)
      } else {
        data = await apiGenerateDesign({ prompt, style })
        set({
          design: data.design,
          activeProjectId: data.project_id,
          activeVersionId: data.design_id,
        })
        toast.success('Project created and design generated! ✨')
      }

      await loadProjectsList({ showLoader: false })
    } catch (err) {
      toast.error(getGenerationErrorMessage(err))
    } finally {
      set({ loading: false })
    }
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
