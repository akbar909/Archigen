import { useEffect, useRef, useState } from 'react'

const STYLE_CATEGORIES = [
  { id: 'modern',     label: 'Modern',     emoji: '🏙️' },
  { id: 'minimal',    label: 'Minimal',    emoji: '⬜' },
  { id: 'classic',    label: 'Classic',    emoji: '🏛️' },
  { id: 'industrial', label: 'Industrial', emoji: '🏗️' },
  { id: 'biophilic',  label: 'Biophilic',  emoji: '🌿' },
  { id: 'coastal',    label: 'Coastal',    emoji: '🌊' },
]

const QUICK_PROMPTS = [
  'Cozy 2-bedroom loft with open living area',
  '5-bedroom coastal villa with breezeways',
  'Modern penthouse with rooftop terrace',
  'Compact smart home with modular rooms',
  'Mediterranean villa with inner courtyard',
]

const SendIcon = ({ loading }) => loading ? (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ animation: 'spin 1s linear infinite' }}>
    <path d="M21 12a9 9 0 11-6.219-8.56" />
  </svg>
) : (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
  </svg>
)

export default function ChatInput({ onSend, loading, disabled, showQuickPrompts = true }) {
  const [prompt, setPrompt] = useState('')
  const [style, setStyle] = useState('modern')
  const textareaRef = useRef(null)

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
  }, [prompt])

  const handleSubmit = () => {
    if (!prompt.trim() || loading) return
    onSend({ prompt: prompt.trim(), style, timeout: 60 })
    setPrompt('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="input-wrapper">
      {/* Quick Prompts — shown only when textarea is empty */}
      {showQuickPrompts && !prompt && !loading && (
        <div className="quick-prompts fade-up">
          {QUICK_PROMPTS.map(p => (
            <button
              key={p}
              className="quick-prompt-btn"
              onClick={() => { setPrompt(p); textareaRef.current?.focus() }}
              type="button"
            >
              {p}
            </button>
          ))}
        </div>
      )}

      {/* Main Input Box */}
      <div className="input-container">
        <textarea
          ref={textareaRef}
          id="design-prompt-input"
          className="input-textarea scroll-soft"
          placeholder='Describe your dream space… e.g. "A modern 3-bedroom house with open kitchen and garden view"'
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={disabled || loading}
        />

        <div className="input-bottom-row">
          {/* Style category pills */}
          <div className="style-pills">
            {STYLE_CATEGORIES.map(cat => (
              <button
                key={cat.id}
                type="button"
                className={`style-pill ${style === cat.id ? 'active' : ''}`}
                onClick={() => setStyle(cat.id)}
                title={cat.label}
              >
                <span style={{ fontSize: '0.875em' }}>{cat.emoji}</span>
                <span>{cat.label}</span>
              </button>
            ))}
          </div>

          {/* Send button */}
          <button
            id="send-design-btn"
            className="send-btn"
            onClick={handleSubmit}
            disabled={!prompt.trim() || loading || disabled}
            title={loading ? 'Generating…' : 'Generate (Enter)'}
            type="button"
          >
            <SendIcon loading={loading} />
          </button>
        </div>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
