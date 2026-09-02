import { toast } from 'react-hot-toast'

export default function JsonViewer({ design }) {
  if (!design) return null

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(design, null, 2))
    toast.success('Copied to clipboard!')
  }

  return (
    <div className="json-card fade-up">
      <div className="json-card-header">
        <div>
          <div className="viewer-card-title">Design JSON Output</div>
          <div className="viewer-card-sub">Structured layout data · Ready for downstream tools</div>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          style={{
            background: 'var(--bg-tertiary)',
            border: '1px solid var(--border)',
            color: 'var(--text-secondary)',
            borderRadius: 'var(--radius-sm)',
            padding: '5px 12px',
            fontSize: '0.75rem',
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          Copy JSON
        </button>
      </div>
      <pre className="json-body scroll-soft">
        {JSON.stringify(design, null, 2)}
      </pre>
    </div>
  )
}
