import axios from 'axios'

// const API_BASE = 'http://localhost:5000/api'
const API_BASE = 'https://huggingface.co/spaces/akbar909/archigen'

const client = axios.create({
  baseURL: API_BASE,
  timeout: 90000,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('archigen_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ── Auth ──────────────────────────────────────────────────────────────
export async function register(payload) {
  const { data } = await client.post('/auth/register', payload)
  return data
}

export async function login(payload) {
  const { data } = await client.post('/auth/login', payload)
  return data
}

// ── Legacy (still used for quick single-shot generation) ──────────────
export async function generateDesign(payload) {
  const { data } = await client.post('/chat', payload)
  return data
}

export async function fetchHistory() {
  const { data } = await client.get('/history')
  return data
}

export async function fetchDesign(id) {
  const { data } = await client.get(`/design/${id}`)
  return data
}

// ── Projects ──────────────────────────────────────────────────────────
export async function fetchProjects() {
  const { data } = await client.get('/projects')
  return data   // { projects: [...] }
}

export async function createProject(payload) {
  // payload: { name, style }
  const { data } = await client.post('/projects', payload)
  return data   // { success, project }
}

export async function renameProject(projectId, name) {
  const { data } = await client.patch(`/projects/${projectId}`, { name })
  return data
}

export async function deleteProject(projectId) {
  const { data } = await client.delete(`/projects/${projectId}`)
  return data
}

// ── Versions ──────────────────────────────────────────────────────────
export async function fetchVersions(projectId) {
  const { data } = await client.get(`/projects/${projectId}/versions`)
  return data   // { versions: [...] }
}

export async function fetchVersion(versionId) {
  const { data } = await client.get(`/versions/${versionId}`)
  return data   // { version: { ... design ... } }
}

export async function generateVersion(projectId, payload) {
  // payload: { prompt, style }
  const { data } = await client.post(`/projects/${projectId}/generate`, payload)
  return data   // { success, version }
}
