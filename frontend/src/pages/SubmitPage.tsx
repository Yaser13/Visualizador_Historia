import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, isAbort, toApiError } from '../api/client'
import { createSubmission } from '../api/endpoints'
import { useSessionExpiry } from '../auth/authContext'
import { ErrorSummary, Field, SubmitButton } from '../components/forms'
import { isHttpUrl, useFormFeedback } from '../components/formState'
import type { FieldDef } from '../components/formState'
import { PageFrame } from '../components/PageStates'
import type { StorySummary } from '../components/storyTypes'
import { href, navigate } from '../router'

const FIELDS: FieldDef[] = [
  { name: 'url', label: 'Enlace de la noticia' },
  { name: 'note', label: 'Nota para el equipo' },
  { name: 'target_story', label: 'Cronología' },
]
/** `geopolitica` is a reserved standalone story, not a `TimelineStory` (CONTRATO_CRONOLOGIAS.md §5). */
const NOT_TIMELINES = new Set(['geopolitica'])

type StoriesState = { status: 'loading' } | { status: 'error' } | { status: 'success'; stories: StorySummary[] }

export default function SubmitPage() {
  const onSessionError = useSessionExpiry()
  const form = useFormFeedback('submit', FIELDS)
  const [url, setUrl] = useState('')
  const [note, setNote] = useState('')
  const [target, setTarget] = useState('')
  const [pending, setPending] = useState(false)
  const [stories, setStories] = useState<StoriesState>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    api.get<{ stories?: unknown }>('/api/stories/', controller.signal)
      .then(({ data }) => {
        const items = Array.isArray(data?.stories) ? (data.stories as StorySummary[]).filter((item) => item && typeof item.slug === 'string' && typeof item.title === 'string' && !NOT_TIMELINES.has(item.slug)) : []
        setStories({ status: 'success', stories: items })
      })
      .catch((error) => { if (!isAbort(error)) setStories({ status: 'error' }) })
    return () => controller.abort()
  }, [])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (pending) return
    const trimmed = url.trim()
    const errors: Record<string, string[]> = {}
    if (!trimmed) errors.url = ['Pega el enlace de la noticia.']
    else if (!isHttpUrl(trimmed)) errors.url = ['Usa una dirección completa que empiece por http:// o https://.']
    else if (trimmed.length > 1000) errors.url = ['La dirección es demasiado larga (máximo 1000 caracteres).']
    if (note.length > 1000) errors.note = ['Usa como máximo 1000 caracteres.']
    if (Object.keys(errors).length) { form.fail(errors); return }
    setPending(true)
    form.clear()
    try {
      const { duplicate, submission } = await createSubmission({ url: trimmed, ...(note.trim() ? { note: note.trim() } : {}), ...(target ? { target_story: target } : {}) })
      navigate(`/envios/${submission.id}${duplicate ? '?existente=1' : ''}`)
    } catch (error) {
      const apiError = toApiError(error)
      onSessionError(apiError)
      if (apiError.status === 429) form.fail({}, [apiError.detail ?? 'Has alcanzado el límite diario de envíos. Podrás enviar más noticias mañana.'])
      else form.failWith(apiError)
    } finally {
      setPending(false)
    }
  }

  return (
    <PageFrame eyebrow="CONTRIBUIR" title="Enviar una noticia" wide intro={<p>Comparte el enlace de una noticia de actualidad internacional. La analizaremos con fuentes verificables y, si un editor la aprueba, aparecerá en el globo.</p>}>
      <div className="submit-layout">
        <div>
          <ErrorSummary items={form.summary} attempt={form.attempt} title="No pudimos enviar la noticia" />
          <form className="form-card" noValidate onSubmit={submit} aria-busy={pending}>
            <Field id={form.fieldId('url')} name="url" label="Enlace de la noticia" errors={form.errors.url} hint="Dirección completa del artículo (http o https)." required>
              {(control) => <input {...control} type="url" inputMode="url" autoComplete="url" spellCheck={false} placeholder="https://…" value={url} onChange={(event) => setUrl(event.target.value)} />}
            </Field>
            <Field id={form.fieldId('note')} name="note" label="Nota para el equipo" errors={form.errors.note} hint={`Contexto útil para la revisión. ${note.length} / 1000 caracteres.`}>
              {(control) => <textarea {...control} rows={3} maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} />}
            </Field>
            <Field id={form.fieldId('target_story')} name="target_story" label="Cronología" errors={form.errors.target_story}
              hint={stories.status === 'error' ? 'No pudimos cargar las cronologías; puedes enviar la noticia sin elegir una.' : 'Añade la observación como hito de una cronología existente o deja que se cree una nueva.'}>
              {(control) => (
                <select {...control} value={target} onChange={(event) => setTarget(event.target.value)} disabled={stories.status !== 'success'}>
                  <option value="">{stories.status === 'loading' ? 'Cargando cronologías…' : 'Ninguna: crear una cronología nueva'}</option>
                  {stories.status === 'success' && stories.stories.map((story) => <option key={story.slug} value={story.slug}>{story.title}{story.origin === 'ai_pipeline' ? ' (IA)' : ''}</option>)}
                </select>
              )}
            </Field>
            <div className="form-actions">
              <SubmitButton pending={pending} pendingLabel="Enviando…">Enviar noticia</SubmitButton>
              <a className="button button-quiet" href={href('/envios')}>Ver mis envíos</a>
            </div>
          </form>
        </div>
        <aside className="process-card" aria-labelledby="process-title">
          <h2 id="process-title">Qué ocurre después</h2>
          <ol className="process-list">
            <li><strong>Descarga.</strong> El servidor descarga la página enviada y guarda su texto.</li>
            <li><strong>Cobertura relacionada.</strong> Busca fuentes independientes sobre el mismo acontecimiento.</li>
            <li><strong>Extracción y verificación.</strong> Agentes de IA proponen afirmaciones; solo se conservan las que tienen una cita literal encontrada en el texto descargado.</li>
            <li><strong>Ubicación y análisis.</strong> Se ubican los lugares mencionados (referencias aproximadas) y se redacta un análisis etiquetado como asistido por IA.</li>
            <li><strong>Revisión humana.</strong> Un editor revisa el borrador y decide si se publica.</li>
          </ol>
          <div className="guarantee">
            <p className="guarantee-title">Garantías</p>
            <p>Solo se publican afirmaciones con cita literal de fuentes descargadas; un editor revisa antes de publicar.</p>
            <p>La IA no aporta enlaces, fechas, cifras ni coordenadas que no estén en las fuentes. Puedes seguir cada paso en «Mis envíos».</p>
          </div>
        </aside>
      </div>
    </PageFrame>
  )
}
