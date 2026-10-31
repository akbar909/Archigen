import { useEffect, useRef, useState } from 'react'
import {
  Building,
  Factory,
  Landmark,
  Leaf,
  Loader2,
  Minimize,
  Send,
  Sparkles,
  Waves,
} from 'lucide-react'

const STYLE_CATEGORIES = [
  { id: 'modern', label: 'Modern', icon: Building },
  { id: 'minimal', label: 'Minimal', icon: Minimize },
  { id: 'classic', label: 'Classic', icon: Landmark },
  { id: 'industrial', label: 'Industrial', icon: Factory },
  { id: 'biophilic', label: 'Biophilic', icon: Leaf },
  { id: 'coastal', label: 'Coastal', icon: Waves },
]

const QUICK_PROMPTS = [
  'Cozy 2-bedroom loft with open living area',
  '5-bedroom coastal villa with breezeways',
  'Modern penthouse with rooftop terrace',
  'Compact smart home with modular rooms',
  'Mediterranean villa with inner courtyard',
]

export default function ChatInput({ onSend, onOpenWizard, loading, disabled, showQuickPrompts = true }) {
  const [prompt, setPrompt] = useState('')
  const [style, setStyle] = useState('modern')
  const textareaRef = useRef(null)

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'
  }, [prompt])

  const handleSubmit = () => {
    if (!prompt.trim() || loading || disabled) return
    onSend({ prompt: prompt.trim(), style, timeout: 120 })
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
      {/* Quick prompt suggestions */}
      {showQuickPrompts && (
        <div className="quick-prompts">
          {QUICK_PROMPTS.map((qp) => (
            <button
              key={qp}
              type="button"
              className="quick-prompt-btn"
              onClick={() => setPrompt(qp)}
            >
              {qp}
            </button>
          ))}
        </div>
      )}

      {/* Main input container */}
      <div className="input-container">
        <textarea
          ref={textareaRef}
          id="design-prompt-input"
          aria-label="Describe your design or changes"
          className="input-textarea"
          rows={1}
          placeholder='Describe your dream space... e.g. "A modern 3-bedroom house with open kitchen and garden view"'
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled || loading}
        />

        <div className="input-bottom-row">
          {/* Style category pills with real Lucide icons */}
          <div className="style-pills">
            {STYLE_CATEGORIES.map((cat) => {
              const IconComponent = cat.icon
              const isActive = style === cat.id
              return (
                <button
                  key={cat.id}
                  type="button"
                  className={`style-pill ${isActive ? 'active' : ''}`}
                  onClick={() => setStyle(cat.id)}
                  title={cat.label}
                  style={{ display: 'flex', alignItems: 'center', gap: 5 }}
                >
                  <IconComponent size={13} strokeWidth={isActive ? 2.2 : 1.8} />
                  <span>{cat.label}</span>
                </button>
              )
            })}
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 'auto' }}>
            {onOpenWizard && (
              <button
                type="button"
                onClick={onOpenWizard}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/25 hover:border-emerald-500/50 transition-all cursor-pointer"
                title="Open interactive multi-step design wizard"
              >
                <Sparkles size={13} />
                <span className="hidden sm:inline">Design</span> Wizard
              </button>
            )}

            {/* Send button */}
            <button
              id="send-design-btn"
              className="send-btn"
              onClick={handleSubmit}
              disabled={!prompt.trim() || loading || disabled}
              title={loading ? 'Generating…' : 'Generate (Enter)'}
              type="button"
            >
            {loading ? (
              <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
            ) : (
              <Send size={15} />
            )}
          </button>
        </div>
      </div>
    </div>
    </div>
  )
}
