import { useState } from 'react'
import type { ReactNode } from 'react'
import { toApiError } from '../api/client'
import { retrySubmission } from '../api/endpoints'
import type { SubmissionDetail } from '../api/types'
import { useAuth, useSessionExpiry } from '../auth/authContext'
import { StatusBadge } from '../components/Badges'
import EventCard from '../components/EventCard'
import { AGENT_LABELS, formatDateTime, statusLabel } from '../components/format'
import { isHttpUrl } from '../components/formState'
import { ErrorState, LoadingState, PageFrame } from '../components/PageStates'
import PipelineSteps from '../components/PipelineSteps'
import ReviewPanel from '../components/ReviewPanel'
import { href } from '../router'
import { useSubmissionPolling } from './useSubmissionPolling'

const ROLE_LABELS: Record<string, string> = { submitted: 'Enlace enviado', related: 'Cobertura relacionada' }
const RUN_LABELS: Record<string, string> = { ok: 'Completado', error: 'Error', skipped: 'Omitido' }
/** Statuses after the research step, when the related coverage is already known. */
const AFTER_RESEARCH = new Set(['extracting', 'verifying', 'geolocating', 'analyzing', 'review', 'published', 'rejected'])

const ExternalLink = ({ url, children }: { url: string; children: ReactNode }) => isHttpUrl(url)
  ? <a href={url} target="_blank" rel="noreferrer noopener">{children} <span aria-hidden="true">↗</span><span className="sr-only"> (se abre en una pestaña nueva)</span></a>
  : <>{children}</>

function Documents({ data }: { data: SubmissionDetail }) {
  const related = data.documents.filter((doc) => doc.role === 'related' && !doc.fetch_error).length
  return (
    <section className="detail-section" aria-labelledby="documents-title">
      <h2 id="documents-title">Documentos consultados <span className="count">({data.documents.length})</span></h2>
      {AFTER_RESEARCH.has(data.status) && related === 0 && <p className="notice notice-warning">Fuente única: no se descargó cobertura relacionada independiente. Las afirmaciones dependen solo del enlace enviado.</p>}
      {data.documents.length === 0
        ? <p className="muted">Todavía no se ha descargado ningún documento.</p>
        : <ul className="document-list">
          {data.documents.map((doc, index) => {
            const published = formatDateTime(doc.published_at)
            const fetched = formatDateTime(doc.fetched_at)
            return (
              <li key={`${doc.url}-${index}`} className={doc.fetch_error ? 'document is-error' : 'document'}>
                <p className="document-role">{ROLE_LABELS[doc.role] ?? doc.role}</p>
                <p className="document-title"><ExternalLink url={doc.url}>{doc.title || doc.url}</ExternalLink></p>
                <p className="document-meta">
                  <span>{doc.publisher || 'Editor no identificado'}</span>
                  <span>{published ? <>Publicado: {published}</> : 'Fecha de publicación no consta en el documento'}</span>
                  {fetched && <span>Descargado: {fetched}</span>}
                </p>
                {doc.fetch_error && <p className="document-error">No se pudo descargar: {doc.fetch_error}</p>}
              </li>
            )
          })}
        </ul>}
    </section>
  )
}

function AgentRuns({ data }: { data: SubmissionDetail }) {
  return (
    <section className="detail-section" aria-labelledby="agents-title">
      <h2 id="agents-title">Agentes ejecutados <span className="count">({data.agent_runs.length})</span></h2>
      {data.agent_runs.length === 0
        ? <p className="muted">Ningún agente se ha ejecutado todavía.</p>
        : <ul className="agent-list">
          {data.agent_runs.map((run, index) => {
            const finished = formatDateTime(run.finished_at)
            return (
              <li key={`${run.agent}-${index}`} className={`agent-run is-${run.status}`}>
                <span className="agent-name">{AGENT_LABELS[run.agent] ?? run.agent}</span>
                <span className="agent-status">{RUN_LABELS[run.status] ?? run.status}</span>
                <span className="agent-meta">{[run.model && `Modelo: ${run.model}`, finished && `Finalizado: ${finished}`].filter(Boolean).join(' · ')}</span>
                {run.error && <span className="agent-error">{run.error}</span>}
              </li>
            )
          })}
        </ul>}
    </section>
  )
}

function Preview({ data }: { data: SubmissionDetail }) {
  if (!data.preview) {
    const message = data.status === 'failed' || data.status === 'rejected'
      ? 'No hay un borrador disponible para este envío.'
      : 'El borrador aparecerá aquí cuando termine el análisis.'
    return <section className="detail-section" aria-labelledby="preview-title"><h2 id="preview-title">Borrador</h2><p className="muted">{message}</p></section>
  }
  const published = data.status === 'published'
  const event = { ...data.preview, origin: data.preview.origin ?? 'ai_pipeline', submitted_by: data.preview.submitted_by ?? data.submitted_by }
  return (
    <section className="detail-section draft-preview" aria-labelledby="preview-title">
      <h2 id="preview-title">{published ? 'Observación publicada' : 'Vista previa del borrador'}</h2>
      {published
        ? <p className="draft-banner is-published"><strong>PUBLICADA</strong><span>Este contenido ya es visible en el globo.</span></p>
        : <p className="draft-banner"><strong>{data.status === 'rejected' ? 'BORRADOR RECHAZADO — no publicado' : 'BORRADOR — pendiente de revisión'}</strong><span>No es público. Solo lo ven quien lo envió y el equipo editorial. Puede contener errores hasta que un editor lo revise.</span></p>}
      <EventCard event={event} index={0} total={1} draft={!published} inPageAnchors={false} className="event-card preview-card" />
    </section>
  )
}

export default function SubmissionDetailPage({ id, duplicate = false, mode }: { id: number; duplicate?: boolean; mode: 'own' | 'review' }) {
  const { me } = useAuth()
  const onSessionError = useSessionExpiry()
  const { state, reload } = useSubmissionPolling(id, onSessionError)
  const [notice, setNotice] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)
  const [retryError, setRetryError] = useState<string | null>(null)

  const data = state.status === 'success' ? state.data : null
  const polling = state.status === 'success' && state.polling
  const pollError = state.status === 'success' ? state.pollError : null
  const back = mode === 'review' ? { path: '/revision', label: 'Volver a la cola de revisión' } : { path: '/envios', label: 'Volver a mis envíos' }

  const retry = async () => {
    if (retrying) return
    setRetrying(true)
    setRetryError(null)
    try {
      await retrySubmission(id)
      setNotice('El envío ha vuelto a la cola de análisis.')
      reload()
    } catch (error) {
      const apiError = toApiError(error)
      onSessionError(apiError)
      setRetryError(apiError.userMessage)
    } finally {
      setRetrying(false)
    }
  }

  return (
    <PageFrame eyebrow={mode === 'review' ? 'EQUIPO EDITORIAL · REVISIÓN' : 'CONTRIBUIR · DETALLE DEL ENVÍO'} title={data?.event_title || `Envío n.º ${id}`} wide>
      <p className="back-link"><a href={href(back.path)}><span aria-hidden="true">← </span>{back.label}</a></p>
      {duplicate && <p className="notice" role="status">Ya tenías un envío activo con esta misma dirección, así que te mostramos ese envío en lugar de crear uno nuevo.</p>}
      {notice && <p className="notice notice-success" role="status">{notice}</p>}
      {state.status === 'loading' && <LoadingState>Cargando el envío…</LoadingState>}
      {state.status === 'error' && <ErrorState message={state.error.status === 404 ? 'Este envío no existe o no tienes acceso a él.' : state.error.userMessage} onRetry={state.error.status === 404 ? undefined : reload}>
        {state.error.status === 404 && <p><a href={href(back.path)}>{back.label}</a></p>}
      </ErrorState>}
      {data && <>
        <section className="detail-summary" aria-label="Datos del envío">
          <div className="detail-status"><StatusBadge status={data.status} label={data.status_label} /></div>
          <dl>
            <dt>Enlace enviado</dt><dd className="break"><ExternalLink url={data.url}>{data.url}</ExternalLink></dd>
            {(mode === 'review' || me?.is_staff) && <><dt>Enviado por</dt><dd>{data.submitted_by ?? 'No disponible'}</dd></>}
            {data.note && <><dt>Nota</dt><dd>{data.note}</dd></>}
            <dt>Enviado</dt><dd>{formatDateTime(data.created_at) ?? 'Fecha no disponible'}</dd>
            <dt>Última actualización</dt><dd>{formatDateTime(data.updated_at) ?? 'Fecha no disponible'}</dd>
          </dl>
        </section>

        <section className="detail-section" aria-labelledby="progress-title">
          <h2 id="progress-title">Progreso del análisis</h2>
          <PipelineSteps status={data.status} runs={data.agent_runs} />
          {data.step_detail && <p className="step-detail">{data.step_detail}</p>}
          {polling && <p className="poll-hint"><span className="spinner" aria-hidden="true" /> Se actualiza automáticamente cada 4 segundos.</p>}
          {pollError && <p className="notice notice-warning">No pudimos actualizar el estado: {pollError.userMessage}{polling ? ' Lo intentaremos de nuevo automáticamente.' : ''}</p>}
          <p className="sr-only" aria-live="polite">Estado: {statusLabel(data.status, data.status_label)}</p>
          {data.status === 'failed' && <div className="failure-box">
            <p className="failure-title">El análisis se detuvo.</p>
            <p>{data.error || 'No hay detalles del error.'}</p>
            {mode === 'own' && <button type="button" className="button button-primary" onClick={retry} aria-disabled={retrying || undefined}>{retrying ? 'Reintentando…' : 'Reintentar'}</button>}
            {retryError && <p className="field-error" role="alert">{retryError}</p>}
          </div>}
          {data.status === 'rejected' && <div className="failure-box"><p className="failure-title">El equipo editorial rechazó este borrador.</p><p>{data.review_note || 'Sin nota de revisión.'}</p></div>}
          {data.status === 'published' && <div className="success-box">
            <p>Observación publicada{data.review_note ? <> · Nota del equipo: {data.review_note}</> : null}.</p>
            {data.story_slug && <p><a className="button button-primary" href={`#noticia=${encodeURIComponent(data.story_slug)}`}>Ver en el globo</a></p>}
          </div>}
        </section>

        {me?.is_staff && data.status === 'review' && <ReviewPanel id={id} onError={onSessionError} onDone={(message) => { setNotice(message); reload() }} />}
        <Preview data={data} />
        <Documents data={data} />
        <AgentRuns data={data} />
      </>}
    </PageFrame>
  )
}
