import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store'

export default function AuthPage() {
  const [isRegister, setIsRegister] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)

  const navigate = useNavigate()
  const { isAuthed, login, register } = useAuthStore()

  useEffect(() => {
    if (isAuthed) {
      navigate('/app', { replace: true })
    }
  }, [isAuthed, navigate])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)

    try {
      const payload = { email, password }
      if (isRegister) payload.name = name

      const result = isRegister ? await register(payload) : await login(payload)
      if (result.success) {
        navigate('/app')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      {/* Nav */}
      <nav className="auth-page-nav">
        <button
          type="button"
          onClick={() => navigate('/')}
          style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Back to Home</span>
        </button>
        <div className="sidebar-logo" style={{ fontSize: '1.125rem' }}>
          Archi<span style={{ color: 'var(--accent)' }}>Gen</span>
        </div>
        <div style={{ width: 80 }} />
      </nav>

      {/* Body */}
      <div className="auth-body">
        <div className="auth-card fade-up">
          {/* Header */}
          <div>
            <div className="auth-card-title">
              {isRegister ? 'Create your account' : 'Welcome back'}
            </div>
            <div className="auth-card-sub">
              {isRegister
                ? 'Start designing architectural spaces with AI'
                : 'Sign in to your ArchiGen workspace'}
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {isRegister && (
              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input
                  id="auth-name"
                  className="form-input"
                  type="text"
                  placeholder="John Architect"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  autoComplete="name"
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Email Address</label>
              <input
                id="auth-email"
                className="form-input"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Password</label>
              <input
                id="auth-password"
                className="form-input"
                type="password"
                placeholder={isRegister ? 'Min. 8 characters' : '••••••••'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete={isRegister ? 'new-password' : 'current-password'}
              />
            </div>

            <button
              id="auth-submit-btn"
              type="submit"
              className="auth-submit-btn"
              disabled={loading}
              style={{ opacity: loading ? 0.75 : 1, marginTop: 4 }}
            >
              {loading
                ? 'Please wait…'
                : isRegister
                ? 'Create Account & Start Designing'
                : 'Sign In'}
            </button>
          </form>

          <div className="auth-divider">
            <div className="auth-divider-text">or</div>
          </div>

          {/* Switch mode */}
          <div className="auth-switch">
            {isRegister ? 'Already have an account? ' : "Don't have an account? "}
            <button
              id="auth-toggle-btn"
              className="auth-switch-btn"
              onClick={() => setIsRegister((v) => !v)}
              type="button"
            >
              {isRegister ? 'Sign In' : 'Sign Up Free'}
            </button>
          </div>

          {/* Terms note */}
          {isRegister && (
            <div style={{ fontSize: '0.7375rem', color: 'var(--text-muted)', textAlign: 'center', lineHeight: 1.5 }}>
              By creating an account you agree to our{' '}
              <span style={{ color: 'var(--text-secondary)', cursor: 'pointer' }}>Terms of Service</span>
              {' '}and{' '}
              <span style={{ color: 'var(--text-secondary)', cursor: 'pointer' }}>Privacy Policy</span>.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
