import { useEffect, useState } from 'react'
import { isAbort, toApiError } from '../api/client'
import type { ApiError } from '../api/client'
import { listSubmissions } from '../api/endpoints'
import type { Submission } from '../api/types'
import { useSessionExpiry } from '../auth/authContext'
import { EmptyState, ErrorState, LoadingState, PageFrame } from '../components/PageStates'
import SubmissionList from '../components/SubmissionList'
import { href } from '../router'

type State = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'success'; items: Submission[] }

/** `#/envios` (own submissions) and `#/revision` (staff queue: `?all=1` filtered to `review`). */
export default function SubmissionsPage({ mode }: { mode: 'own' | 'review' }) {
  const onSessionError = useSessionExpiry()
  const [state, setState] = useState<State>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    listSubmissions(mode === 'review', controller.signal)
      .then((items) => setState({ status: 'success', items: mode === 'review' ? items.filter((item) => item.status === 'review') : items }))
      .catch((error) => {
        if (isAbort(error)) return
        const apiError = toApiError(error)
        onSessionError(apiError)
        setState({ status: 'error', error: apiError })
      })
      .finally(() => { if (!controller.signal.aborted) setRefreshing(false) })
    return () => controller.abort()
  }, [mode, attempt, onSessionError])

  const reload = () => { setRefreshing(true); setAttempt((value) => value + 1) }
  const review = mode === 'review'

  return (
    <PageFrame
      eyebrow={review ? 'EQUIPO EDITORIAL' : 'CONTRIBUIR'}
      title={review ? 'Cola de revisión' : 'Mis envíos'}
      wide
      intro={<p>{review
        ? 'Borradores generados a partir de envíos de usuarios que esperan una decisión editorial. Revisa cada afirmación y sus citas antes de publicar.'
        : 'Noticias que has enviado, de la más reciente a la más antigua. Abre un envío para seguir su análisis paso a paso.'}</p>}
    >
      <div className="page-toolbar">
        {!review && <a className="button button-primary" href={href('/enviar')}>Enviar noticia</a>}
        <button type="button" className="button" onClick={reload} aria-disabled={refreshing || undefined} disabled={state.status === 'loading'}>{refreshing ? 'Actualizando…' : 'Actualizar lista'}</button>
        {state.status === 'success' && <p className="page-toolbar-count" role="status">{state.items.length} {review ? (state.items.length === 1 ? 'borrador pendiente' : 'borradores pendientes') : (state.items.length === 1 ? 'envío' : 'envíos')}</p>}
      </div>
      {state.status === 'loading' && <LoadingState>{review ? 'Cargando la cola de revisión…' : 'Cargando tus envíos…'}</LoadingState>}
      {state.status === 'error' && <ErrorState message={state.error.userMessage} onRetry={() => { setState({ status: 'loading' }); setAttempt((value) => value + 1) }} />}
      {state.status === 'success' && (state.items.length
        ? <SubmissionList items={state.items} basePath={review ? '/revision' : '/envios'} showSubmitter={review} />
        : review
          ? <EmptyState title="No hay borradores pendientes de revisión."><p>Cuando un envío termine su análisis aparecerá aquí.</p></EmptyState>
          : <EmptyState title="Todavía no has enviado ninguna noticia."><p><a href={href('/enviar')}>Envía tu primera noticia</a> para que se analice con fuentes verificables.</p></EmptyState>)}
    </PageFrame>
  )
}
