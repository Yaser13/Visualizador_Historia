import { useEffect, useId, useRef, useState } from 'react'
import { toApiError } from '../api/client'
import type { ApiError } from '../api/client'
import { publishSubmission, rejectSubmission } from '../api/endpoints'

type Action = 'publish' | 'reject'

/**
 * Staff decision on a submission in `review`: publish (optional note) or reject (mandatory note),
 * always confirmed in a modal dialog. The server enforces permissions and state.
 */
export default function ReviewPanel({ id, onDone, onError }: { id: number; onDone: (message: string) => void; onError: (error: ApiError) => void }) {
  const [note, setNote] = useState('')
  const [noteError, setNoteError] = useState<string | null>(null)
  const [confirming, setConfirming] = useState<Action | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const dialog = useRef<HTMLDialogElement>(null)
  const noteRef = useRef<HTMLTextAreaElement>(null)
  const ids = useId()

  useEffect(() => {
    const node = dialog.current
    if (!node) return
    if (confirming && !node.open) node.showModal?.()
    if (!confirming && node.open) node.close()
  }, [confirming])

  const ask = (action: Action) => {
    setError(null)
    if (action === 'reject' && !note.trim()) {
      setNoteError('Escribe el motivo del rechazo: es obligatorio y lo verá quien envió la noticia.')
      noteRef.current?.focus()
      return
    }
    setNoteError(null)
    setConfirming(action)
  }

  const confirm = async () => {
    if (!confirming || pending) return
    setPending(true)
    try {
      if (confirming === 'publish') await publishSubmission(id, note.trim())
      else await rejectSubmission(id, note.trim())
      const message = confirming === 'publish' ? 'Observación publicada.' : 'Envío rechazado.'
      setConfirming(null)
      onDone(message)
    } catch (failure) {
      const apiError = toApiError(failure)
      onError(apiError)
      const fieldMessage = apiError.errors.note?.join(' ')
      if (fieldMessage) setNoteError(fieldMessage)
      setError(fieldMessage ? 'Revisa la nota de revisión.' : apiError.userMessage)
      setConfirming(null)
    } finally {
      setPending(false)
    }
  }

  const noteId = `${ids}-note`
  return (
    <section className="review-panel" aria-labelledby={`${ids}-title`}>
      <h2 id={`${ids}-title`}>Decisión editorial</h2>
      <p>Comprueba que cada afirmación coincide con su cita literal y que las fuentes están bien atribuidas. Publicar hace visible la observación en el globo para todo el público.</p>
      <div className={noteError ? 'field has-error' : 'field'}>
        <label htmlFor={noteId}>Nota de revisión <span className="field-flag">(obligatoria para rechazar)</span></label>
        <p className="field-hint" id={`${noteId}-hint`}>Se guarda con la decisión y la ve quien envió la noticia.</p>
        <textarea id={noteId} ref={noteRef} rows={3} maxLength={1000} value={note} onChange={(event) => { setNote(event.target.value); if (noteError && event.target.value.trim()) setNoteError(null) }}
          aria-invalid={noteError ? true : undefined} aria-describedby={[`${noteId}-hint`, noteError ? `${noteId}-error` : null].filter(Boolean).join(' ')} />
        {noteError && <p className="field-error" id={`${noteId}-error`}><span aria-hidden="true">⚠ </span>{noteError}</p>}
      </div>
      {error && <p className="notice notice-error" role="alert">{error}</p>}
      <div className="form-actions">
        <button type="button" className="button button-primary" onClick={() => ask('publish')}>Publicar…</button>
        <button type="button" className="button button-danger" onClick={() => ask('reject')}>Rechazar…</button>
      </div>

      <dialog ref={dialog} className="confirm-dialog" aria-labelledby={`${ids}-dialog-title`} aria-describedby={`${ids}-dialog-text`} onCancel={(event) => { if (pending) event.preventDefault() }} onClose={() => setConfirming(null)}>
        <h2 id={`${ids}-dialog-title`}>{confirming === 'reject' ? '¿Rechazar este envío?' : '¿Publicar esta observación?'}</h2>
        <p id={`${ids}-dialog-text`}>{confirming === 'reject'
          ? 'El borrador no se publicará y el envío quedará marcado como rechazado con tu nota.'
          : 'La observación se mostrará en el globo con la insignia de contenido generado con IA y la autoría de quien la envió.'}</p>
        {note.trim() && <p className="confirm-note"><strong>Nota:</strong> {note.trim()}</p>}
        <div className="form-actions">
          <button type="button" className={confirming === 'reject' ? 'button button-danger' : 'button button-primary'} onClick={confirm} aria-disabled={pending || undefined}>
            {pending ? 'Procesando…' : confirming === 'reject' ? 'Confirmar rechazo' : 'Confirmar publicación'}
          </button>
          <button type="button" className="button" onClick={() => { if (!pending) setConfirming(null) }}>Cancelar</button>
        </div>
      </dialog>
    </section>
  )
}
