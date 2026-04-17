import { useState } from 'react'

const styles = ['modern', 'minimal', 'classic']
const suggestionPresets = [
  'Design a biophilic penthouse with tiered terraces and a double-height atrium.',
  'Craft a coastal family villa with five bedrooms, breezeways, and indoor-outdoor flow.',
  'Generate a compact smart home with modular rooms and adaptive lighting corridors.',
]

export default function ChatPanel({ onSend, loading }) {
  const [prompt, setPrompt] = useState('Design a cozy two-bedroom modern loft with open living area and balcony access.')
  const [style, setStyle] = useState('modern')
  const [timeout, setTimeoutValue] = useState(45)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!prompt.trim()) return
    onSend({ prompt, style, timeout: Number(timeout) })
  }

  return (
    <form onSubmit={handleSubmit} className="glass-card p-4 md:p-5 grid gap-4 border border-slate-700/70">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-sm text-slate-300">Describe your dream space</p>
          <h2 className="text-lg font-semibold text-white">Prompt</h2>
        </div>
        <div className="flex gap-2">
          <select
            value={style}
            onChange={(e) => setStyle(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-slate-100 text-sm rounded-lg px-3 py-2"
          >
            {styles.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <input
            type="number"
            min={5}
            max={180}
            value={timeout}
            onChange={(e) => setTimeoutValue(e.target.value)}
            className="w-24 bg-slate-800 border border-slate-700 text-slate-100 text-sm rounded-lg px-3 py-2"
            title="Request timeout (seconds)"
          />
        </div>
      </div>

      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        rows={5}
        className="w-full bg-slate-900/80 text-slate-100 rounded-xl border border-slate-700 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/70"
        placeholder="e.g., A three-bedroom family house with spacious living room, kitchen island, and two bathrooms in minimal style."
      />

      <div className="flex flex-wrap gap-2">
        {suggestionPresets.map((preset) => (
          <button
            type="button"
            key={preset}
            className="chip px-3 py-2 text-xs text-slate-200"
            onClick={() => setPrompt(preset)}
          >
            {preset}
          </button>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-400">Structured JSON is validated before rendering.</p>
        <button
          type="submit"
          disabled={loading}
          className="inline-flex items-center gap-2 card-cta px-4 py-2 rounded-lg font-semibold shadow-soft disabled:opacity-60"
        >
          {loading ? 'Generating…' : 'Generate Design'}
        </button>
      </div>
    </form>
  )
}
