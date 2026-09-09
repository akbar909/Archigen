import { apiClient } from './apiClient'

export async function fetchProjects() {
  const { data } = await apiClient.get('/projects')
  return data // { projects: [...] }
}

export async function fetchProject(projectId) {
  const { data } = await apiClient.get(`/projects/${projectId}`)
  return data // { project, versions }
}

export async function createProject(payload) {
  // payload: { name, style }
  const { data } = await apiClient.post('/projects', payload)
  return data // { success, project }
}

export async function renameProject(projectId, name) {
  const { data } = await apiClient.patch(`/projects/${projectId}`, { name })
  return data
}

export async function deleteProject(projectId) {
  const { data } = await apiClient.delete(`/projects/${projectId}`)
  return data
}

export async function fetchHistory() {
  const { data } = await apiClient.get('/history')
  return data
}

export async function fetchDesign(id) {
  const { data } = await apiClient.get(`/design/${id}`)
  return data
}
