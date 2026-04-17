import { useState } from 'react'

export default function AuthPanel({ onAuth, mode = 'login' }) {
  const [email, setEmail] = useState('demo@archigen.ai')
  const [password, setPassword] = useState('password123')
  const [name, setName] = useState('Demo User')
  const [isRegister, setIsRegister] = useState(mode === 'register')

  const handleSubmit = (e) => {
    e.preventDefault()
    const payload = { email, password }
    if (isRegister) payload.name = name
    onAuth(isRegister ? 'register' : 'login', payload)
  }

  return (
    <form onSubmit={handleSubmit} className="glass-card p-5 md:p-6 grid gap-4 text-slate-100 border border-slate-700/70">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-400">Secure your workspace</p>
          <h2 className="text-xl font-semibold">{isRegister ? 'Create account' : 'Sign in'}</h2>
        </div>
        <button
          type="button"
          onClick={() => setIsRegister((prev) => !prev)}
          className="text-accent text-sm"
        >
          {isRegister ? 'Use existing account' : 'Create account'}
        </button>
      </div>

      {isRegister && (
        <div className="grid gap-1">
          <label className="text-sm text-slate-300">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="bg-slate-900/80 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent/60"
            required
          />
        </div>
      )}

      <div className="grid gap-1">
        <label className="text-sm text-slate-300">Email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="bg-slate-900/80 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent/60"
          required
        />
      </div>

      <div className="grid gap-1">
        <label className="text-sm text-slate-300">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="bg-slate-900/80 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent/60"
          required
        />
      </div>

      <button
        type="submit"
        className="mt-2 card-cta rounded-lg font-semibold shadow-soft py-3 text-center"
      >
        {isRegister ? 'Sign up & start designing' : 'Sign in'}
      </button>
    </form>
  )
}
