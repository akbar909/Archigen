import React from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import DashboardPage from '../src/pages/DashboardPage'
import { useProjectStore, useAuthStore } from '../src/store'
import { apiClient, setUnauthorizedHandler } from '../src/services/apiClient'
import '../src/index.css'
apiClient.defaults.baseURL = '/api'
setUnauthorizedHandler(() => {})
const design = { layout_approved: true, glb_url: `${location.origin}/asset-test/architecture/walls/designs/wall_panel_01.glb?mobileSlow=1`,
  rooms: [{ id: 'living', name: 'Living room', type: 'living', position: { x: 0, y: 0, z: 0 }, dimensions: { width: 8, depth: 8, height: 3 } }],
  floors: [{ id: 'ground', level: 0 }, { id: 'upper', level: 1 }], building: { floor_height: 3 } }
const projects = Array.from({ length: 24 }, (_, i) => ({ id: i ? `p${i}` : 'mobile', name: `Mobile test project ${i + 1}`, versions: [{ id: 'v1', version_num: 1 }] }))
useProjectStore.setState({ design, persistedDesign: structuredClone(design), projects, activeProjectId: 'mobile', activeVersionId: 'v1',
  loading: false, isVersionLoading: false, sidebarLoading: false, activeTab: 'viewer', sidebarOpen: false,
  loadProjectsList: async () => {}, generate: async () => { window.mobileSent = true; return null } })
useAuthStore.setState({ isAuthed: true, user: { name: 'Mobile Architect', email: 'architect.long.email@example.com' } })
window.mobileStore = useProjectStore
window.mobileAuth = useAuthStore
window.mobileFlashes = []
new MutationObserver(() => {
  const viewer = document.querySelector('.viewer-container')
  if (viewer?.getAttribute('aria-busy') === 'true' && viewer.querySelector('.viewer-editor-actions, .room-navigator, .walkthrough-touch-controls')) window.mobileFlashes.push('controls before readiness')
}).observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['aria-busy'] })
createRoot(document.getElementById('root')).render(<MemoryRouter initialEntries={['/app/projects/mobile/versions/v1']}>
  <Routes><Route path="/app/projects/:projectId/versions/:versionId" element={<DashboardPage />} /></Routes>
</MemoryRouter>)
