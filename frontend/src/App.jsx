import { Toaster } from 'react-hot-toast'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuthStore } from './store'
import { AuthPage, DashboardPage, LandingPage, ModelGalleryPage } from './pages'

function App() {
  const isAuthed = useAuthStore((state) => state.isAuthed)

  return (
    <>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'var(--bg-secondary)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.875rem',
            fontFamily: 'Inter, sans-serif',
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
          },
          success: { iconTheme: { primary: '#10a37f', secondary: 'white' } },
          error: { iconTheme: { primary: '#ef4444', secondary: 'white' } },
        }}
      />

      <Routes>
        {/* Landing page — accessible to everyone */}
        <Route path="/" element={<LandingPage />} />

        {/* 3D Model gallery inspection */}
        <Route path="/models" element={<ModelGalleryPage />} />

        {/* Auth page — redirects to /app if already signed in */}
        <Route
          path="/auth"
          element={isAuthed ? <Navigate to="/app" replace /> : <AuthPage />}
        />

        {/* Main application workspace — requires authentication */}
        <Route
          path="/app"
          element={isAuthed ? <DashboardPage /> : <Navigate to="/auth" replace />}
        />

        {/* Catch-all fallback */}
        <Route path="*" element={<Navigate to={isAuthed ? '/app' : '/'} replace />} />
      </Routes>
    </>
  )
}

export default App
