import { statusLabel, statusTone } from './format'

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  return <span className={`status-badge is-${statusTone(status)}`}><span className="status-dot" aria-hidden="true" />{statusLabel(status, label)}</span>
}

/**
 * Mandatory notice for observations with `origin === 'ai_pipeline'` (CONTRATO_USUARIOS_INGESTA.md §4).
 * Drafts say «pendiente de revisión» instead of «revisada por el equipo», which would not yet be true.
 */
export function AiBadge({ submittedBy, draft = false }: { submittedBy?: string | null; draft?: boolean }) {
  return (
    <p className="ai-badge">
      <span className="ai-badge-mark" aria-hidden="true">IA</span>
      <span>
        Observación generada con IA a partir de las fuentes enlazadas
        {submittedBy ? <> · enviada por {submittedBy}</> : null}
        {draft ? ' · pendiente de revisión del equipo' : ' · revisada por el equipo'}
      </span>
    </p>
  )
}
