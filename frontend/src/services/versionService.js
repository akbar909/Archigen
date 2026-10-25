import { apiClient } from './apiClient'

export async function fetchVersions(projectId) {
  const { data } = await apiClient.get(`/projects/${projectId}/versions`)
  return data // { versions: [...] }
}

export async function fetchVersion(versionId) {
  const { data } = await apiClient.get(`/versions/${versionId}`)
  return data // { version: { ... design ... } }
}

export async function generateVersion(projectId, payload) {
  // payload: { prompt, style, base_version_id, wizard?, timeout? }
  const { data } = await apiClient.post(`/projects/${projectId}/generate`, payload)
  return data // { success, version }
}

export async function generateDesign(payload) {
  // payload: { prompt, style, timeout, wizard? }
  const { data } = await apiClient.post('/chat', payload)
  return data
}

export async function generate3D(projectId, versionId, { force = false } = {}) {
  const { data } = await apiClient.post(
    `/projects/${projectId}/versions/${versionId}/generate-3d`,
    { force }
  )
  return data
}

export async function approveFloorPlan(projectId, versionId) {
  const { data } = await apiClient.post(`/projects/${projectId}/versions/${versionId}/approve-layout`)
  return data
}

export async function updateLayout(projectId, versionId, layoutData) {
  const { data } = await apiClient.patch(`/projects/${projectId}/versions/${versionId}/layout`, {
    design: layoutData,
    layout: layoutData,
  })
  return data
}

export async function fetchLayoutValidation(projectId, versionId) {
  const { data } = await apiClient.get(`/projects/${projectId}/versions/${versionId}/validation`)
  return data
}
