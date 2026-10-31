import React from 'react';
import { createRoot } from 'react-dom/client';
import { Toaster, toast } from 'react-hot-toast';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import DashboardPage from '../src/pages/DashboardPage.jsx';
import { useAuthStore } from '../src/store/useAuthStore.js';
import { useProjectStore } from '../src/store/useProjectStore.js';
import { useFloorPlanEditorStore } from '../src/store/useFloorPlanEditorStore.js';
import { cadFixture } from './cad-fixture.mjs';
import '../src/index.css';
import { apiClient } from '../src/services/apiClient.js';
apiClient.defaults.baseURL = '/api';
const initial = cadFixture();
useProjectStore.setState({
  design: initial,
  persistedDesign: structuredClone(initial),
  activeProjectId: '507f1f77bcf86cd799439011',
  activeVersionId: '507f191e810c19729de860ea',
  projects: [{id:'507f1f77bcf86cd799439011',name:'Courtyard house',versions:[{id:'507f191e810c19729de860ea',version_num:1}]}],
  loadProjectsList: async()=>{}
});
useAuthStore.setState({isAuthed:true,user:{name:'Architect',email:'architect@example.com'}});
window.cadProject = useProjectStore;
window.cadEditor = useFloorPlanEditorStore;
window.cadInitial = initial;
window.dismissCadToasts=()=>toast.remove();
function App() {
  return <MemoryRouter initialEntries={['/app/projects/507f1f77bcf86cd799439011/versions/507f191e810c19729de860ea']}><Routes><Route path="/app/projects/:projectId/versions/:versionId" element={<DashboardPage/>}/></Routes><Toaster/></MemoryRouter>;
}
createRoot(document.getElementById('root')).render(<App />);
