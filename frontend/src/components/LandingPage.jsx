import { useNavigate } from 'react-router-dom'

const features = [
  {
    icon: '🧠',
    title: 'AI-Powered Generation',
    desc: 'Describe any space in natural language. Our AI transforms your words into structured 3D-ready architectural layouts instantly.',
  },
  {
    icon: '🏗️',
    title: 'Live 3D Visualization',
    desc: 'Watch your design come to life in real-time with interactive 3D rendering. Rotate, pan, and zoom to explore every angle.',
  },
  {
    icon: '🎨',
    title: '6 Design Styles',
    desc: 'From Modern and Minimal to Biophilic and Coastal — choose from 6 curated architectural styles to match your vision.',
  },
  {
    icon: '⚡',
    title: 'Lightning Fast',
    desc: 'Average turnaround under 10 seconds. Generate, iterate, and refine designs in a rapid creative flow.',
  },
  {
    icon: '📐',
    title: 'Precise JSON Output',
    desc: 'Every design outputs validated JSON with rooms, doors, windows, and spatial metadata — ready for downstream tools.',
  },
  {
    icon: '📱',
    title: 'Works Everywhere',
    desc: 'Fully responsive across desktop, tablet, and mobile. Design from anywhere, on any device.',
  },
]

const steps = [
  { num: '1', title: 'Describe Your Space', desc: 'Type a natural language prompt — rooms, style, mood, constraints.' },
  { num: '2', title: 'Choose a Style', desc: 'Select from Modern, Minimal, Classic, Industrial, Biophilic, or Coastal.' },
  { num: '3', title: 'Generate & View', desc: 'AI generates a structured layout, rendered live in interactive 3D.' },
  { num: '4', title: 'Iterate & Refine', desc: 'Adjust your prompt, switch styles, and explore your design history.' },
]

const stats = [
  { value: '60fps', label: 'Real-time 3D render' },
  { value: '99.4%', label: 'JSON fidelity score' },
  { value: '8.3s',  label: 'Avg. generation time' },
  { value: '6+',   label: 'Architectural styles' },
]

export default function LandingPage() {
  const navigate = useNavigate()

  return (
    <div style={{ height: '100vh', overflowY: 'auto', background: 'var(--bg-primary)' }}>

      {/* ── Nav ── */}
      <nav className="landing-nav">
        <div style={{ fontFamily: '"Space Grotesk",sans-serif', fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          Archi<span style={{ color: 'var(--accent)' }}>Gen</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            className="btn-secondary"
            style={{ padding: '8px 18px', fontSize: '0.875rem' }}
            onClick={() => navigate('/auth')}
          >
            Sign In
          </button>
          <button
            className="btn-primary"
            style={{ padding: '8px 18px', fontSize: '0.875rem' }}
            onClick={() => navigate('/auth')}
          >
            Get Started →
          </button>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '96px 24px 72px', overflow: 'hidden' }}>
        {/* Glow — behind everything */}
        <div style={{
          position: 'absolute', top: -60, left: '50%', transform: 'translateX(-50%)',
          width: 700, height: 600,
          background: 'radial-gradient(ellipse at 50% 30%, rgba(16,163,127,0.14) 0%, rgba(37,99,235,0.08) 40%, transparent 70%)',
          pointerEvents: 'none', zIndex: 0,
        }} />

        {/* Content — above glow */}
        <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0 }}>
          {/* Badge */}
          <div className="hero-badge fade-up" style={{ marginBottom: 24 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', display: 'inline-block', flexShrink: 0 }} />
            AI Architectural Design
          </div>

          {/* Title */}
          <h1 className="hero-title fade-up fade-up-delay-1">
            Architect-Grade 3D Concepts,{' '}
            <span className="grad">Generated Instantly</span>
          </h1>

          {/* Subtitle */}
          <p className="hero-sub fade-up fade-up-delay-2">
            Describe your dream space in plain language. ArchiGen uses AI to sculpt
            structured 3D-ready floor plans with physically-aware rooms, doors, windows, and flow.
          </p>

          {/* Single CTA */}
          <div className="fade-up fade-up-delay-3" style={{ marginBottom: 56 }}>
            <button className="btn-primary" style={{ padding: '13px 32px', fontSize: '1rem' }} onClick={() => navigate('/auth')}>
              Start Designing Free →
            </button>
          </div>

          {/* Stats Row */}
          <div style={{ display: 'flex', gap: 40, flexWrap: 'wrap', justifyContent: 'center', marginBottom: 56 }} className="fade-up fade-up-delay-3">
            {stats.map(s => (
              <div key={s.label} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '1.625rem', fontWeight: 700, color: 'var(--text-primary)', fontFamily: '"Space Grotesk",sans-serif', letterSpacing: '-0.02em' }}>
                  {s.value}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2 }}>{s.label}</div>
              </div>
            ))}
          </div>

          {/* Preview Window */}
          <div className="preview-window fade-up fade-up-delay-3">
            <div className="preview-titlebar">
              <div className="preview-dot" style={{ background: '#ff5f57' }} />
              <div className="preview-dot" style={{ background: '#febc2e' }} />
              <div className="preview-dot" style={{ background: '#28c840' }} />
              <span style={{ marginLeft: 8, fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                archigen.ai — AI 3D Home Architect
              </span>
            </div>

            {/* Fake app shell preview */}
            <div style={{ display: 'flex', height: 360, background: 'var(--bg-primary)' }}>
              {/* Fake sidebar */}
              <div style={{ width: 200, borderRight: '1px solid var(--border)', background: 'var(--bg-secondary)', padding: 12, display: 'flex', flexDirection: 'column', gap: 8, flexShrink: 0 }}>
                <div style={{ fontWeight: 700, fontSize: '0.875rem', color: 'var(--text-primary)', padding: '4px 0 8px', borderBottom: '1px solid var(--border)', marginBottom: 4 }}>
                  Archi<span style={{ color: 'var(--accent)' }}>Gen</span>
                </div>
                {['Modern Penthouse', 'Coastal Villa', 'Smart Loft'].map((t, i) => (
                  <div key={t} style={{
                    padding: '7px 10px', borderRadius: 6, fontSize: '0.75rem',
                    background: i === 0 ? 'var(--bg-tertiary)' : 'transparent',
                    border: `1px solid ${i === 0 ? 'var(--border-hover)' : 'transparent'}`,
                    color: i === 0 ? 'var(--text-primary)' : 'var(--text-muted)',
                  }}>
                    {t}
                  </div>
                ))}
                <div style={{ flex: 1 }} />
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderTop: '1px solid var(--border)' }}>
                  <div style={{ width: 24, height: 24, borderRadius: '50%', background: 'linear-gradient(135deg,var(--accent),#2563eb)', flexShrink: 0 }} />
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>demo@archigen.ai</div>
                </div>
              </div>

              {/* Fake main area */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                {/* Fake 3D area */}
                <div style={{ flex: 1, background: 'var(--bg-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 8, borderBottom: '1px solid var(--border)' }}>
                  {/* Room blocks */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8, padding: 16 }}>
                    {[
                      { label: 'Living Room', color: '#fbbf24' },
                      { label: 'Kitchen', color: '#f87171' },
                      { label: 'Bedroom 1', color: '#60a5fa' },
                      { label: 'Bedroom 2', color: '#60a5fa' },
                      { label: 'Bathroom', color: '#34d399' },
                      { label: 'Hallway', color: '#c084fc' },
                    ].map(r => (
                      <div key={r.label} style={{
                        background: r.color + '22', border: `1px solid ${r.color}55`,
                        borderRadius: 6, padding: '10px 8px', textAlign: 'center',
                        fontSize: '0.6375rem', color: r.color, fontWeight: 600,
                      }}>
                        {r.label}
                      </div>
                    ))}
                  </div>
                  <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>3D visualization — 6 rooms loaded</div>
                </div>

                {/* Fake input bar */}
                <div style={{ padding: '10px 12px', background: 'var(--bg-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    flex: 1, background: 'var(--bg-input)', border: '1px solid var(--border-hover)',
                    borderRadius: 999, padding: '7px 14px', fontSize: '0.7375rem', color: 'var(--text-muted)'
                  }}>
                    Describe your dream space…
                  </div>
                  <div style={{ width: 30, height: 30, borderRadius: 8, background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.875rem' }}>↑</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section style={{ padding: '80px 24px', maxWidth: 1100, margin: '0 auto' }}>
        <div className="section-label">What's Inside</div>
        <div className="section-title">Everything you need to design smarter</div>
        <div className="features-grid">
          {features.map(f => (
            <div key={f.title} className="feature-card">
              <div className="feature-icon">{f.icon}</div>
              <div>
                <div className="feature-title">{f.title}</div>
                <div className="feature-desc" style={{ marginTop: 6 }}>{f.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── How It Works ── */}
      <section style={{ padding: '72px 24px', background: 'var(--bg-secondary)', borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <div className="section-label">Workflow</div>
          <div className="section-title">How ArchiGen Works</div>
          <div className="steps-grid">
            {steps.map(s => (
              <div key={s.num} className="step">
                <div className="step-num">{s.num}</div>
                <div className="step-title">{s.title}</div>
                <div className="step-desc">{s.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA Banner ── */}
      <section style={{ padding: '96px 24px', textAlign: 'center' }}>
        <div className="section-label">Get Started</div>
        <h2 style={{
          fontFamily: '"Space Grotesk",sans-serif',
          fontSize: 'clamp(2rem,4vw,2.75rem)',
          fontWeight: 700, letterSpacing: '-0.02em',
          color: 'var(--text-primary)', marginBottom: 16, marginTop: 8,
        }}>
          Start designing your dream space today
        </h2>
        <p style={{ fontSize: '1rem', color: 'var(--text-secondary)', marginBottom: 36, maxWidth: 440, margin: '0 auto 36px' }}>
          No credit card required. Generate your first architectural layout free.
        </p>
        <button
          className="btn-primary"
          style={{ padding: '14px 40px', fontSize: '1rem' }}
          onClick={() => navigate('/auth')}
        >
          Create Free Account →
        </button>
      </section>

      {/* ── Footer ── */}
      <footer style={{
        borderTop: '1px solid var(--border)',
        padding: '20px 40px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flexWrap: 'wrap', gap: 12,
      }}>
        <div style={{ fontFamily: '"Space Grotesk",sans-serif', fontWeight: 700, fontSize: '0.9375rem', color: 'var(--text-primary)' }}>
          Archi<span style={{ color: 'var(--accent)' }}>Gen</span>
        </div>
        <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
          © 2026 ArchiGen. AI-powered architectural design.
        </div>
      </footer>
    </div>
  )
}
