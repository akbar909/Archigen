/* eslint-disable react/prop-types */
import { useEffect, useRef, useState } from 'react'
import { GitBranch, Loader2, RefreshCw, Save, X } from 'lucide-react'

export default function SaveVersionModal({
  open,
  currentVersion = 1,
  isSaving = false,
  onClose,
  onSave,
}) {
  const [mode, setMode] = useState('new_version')
  const [note, setNote] = useState('')
  const noteRef = useRef(null)
  const onCloseRef = useRef(onClose)
  const isSavingRef = useRef(isSaving)
  onCloseRef.current = onClose
  isSavingRef.current = isSaving

  useEffect(() => {
    if (!open) return undefined
    setMode('new_version')
    setNote('')
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const focusTimer = window.setTimeout(() => noteRef.current?.focus(), 80)

    const handleKeyDown = (event) => {
      if (event.key === 'Escape' && !isSavingRef.current) onCloseRef.current()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.clearTimeout(focusTimer)
      window.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [open])

  if (!open) return null

  const submit = async (event) => {
    event.preventDefault()
    if (isSaving) return
    await onSave({ mode, note: note.trim() })
  }

  return (
    <div
      className="save-version-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isSaving) onClose()
      }}
    >
      <form
        className="save-version-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="save-version-title"
        onSubmit={submit}
      >
        <div className="save-version-header">
          <div className="save-version-heading">
            <span className="save-version-icon"><Save size={19} /></span>
            <div>
              <h2 id="save-version-title">Save design changes</h2>
              <p>Choose how this draft should be added to project history.</p>
            </div>
          </div>
          <button
            className="save-version-close"
            type="button"
            onClick={onClose}
            disabled={isSaving}
            aria-label="Close save dialog"
          >
            <X size={18} />
          </button>
        </div>

        <fieldset className="save-version-options" disabled={isSaving}>
          <legend>Save mode</legend>
          <label className={`save-version-option ${mode === 'new_version' ? 'selected' : ''}`}>
            <input
              type="radio"
              name="save-mode"
              value="new_version"
              checked={mode === 'new_version'}
              onChange={() => setMode('new_version')}
            />
            <span className="save-version-option-icon"><GitBranch size={18} /></span>
            <span className="save-version-option-copy">
              <strong>Save as Version {currentVersion + 1}</strong>
              <small>Recommended. Keeps Version {currentVersion} unchanged so you can return to it.</small>
            </span>
            <span className="save-version-radio" aria-hidden="true" />
          </label>

          <label className={`save-version-option ${mode === 'overwrite' ? 'selected warning' : ''}`}>
            <input
              type="radio"
              name="save-mode"
              value="overwrite"
              checked={mode === 'overwrite'}
              onChange={() => setMode('overwrite')}
            />
            <span className="save-version-option-icon"><RefreshCw size={18} /></span>
            <span className="save-version-option-copy">
              <strong>Overwrite Version {currentVersion}</strong>
              <small>Replaces this version&apos;s saved layout. Its previous draft will not remain in history.</small>
            </span>
            <span className="save-version-radio" aria-hidden="true" />
          </label>
        </fieldset>

        <label className="save-version-note">
          <span>
            Version note <small>Optional</small>
          </span>
          <textarea
            ref={noteRef}
            value={note}
            onChange={(event) => setNote(event.target.value.slice(0, 500))}
            placeholder="What changed in this design?"
            rows={3}
            maxLength={500}
            disabled={isSaving}
          />
          <small className="save-version-count">{note.length}/500</small>
        </label>

        <div className="save-version-footer">
          <p>
            Save your draft here. Use Build 3D when the layout is ready.
          </p>
          <div className="save-version-actions">
            <button type="button" className="save-version-cancel" onClick={onClose} disabled={isSaving}>
              Cancel
            </button>
            <button type="submit" className="save-version-submit" disabled={isSaving}>
              {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              {isSaving
                ? 'Saving changes…'
                : mode === 'new_version'
                  ? `Save Version ${currentVersion + 1}`
                  : `Overwrite Version ${currentVersion}`}
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
