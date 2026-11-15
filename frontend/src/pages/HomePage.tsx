import { Component, lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import type { ReactNode } from 'react'
import EventCard from '../components/EventCard'
import StorySelector from '../components/StorySelector'
import type { StoryListState } from '../components/StorySelector'
import StoryTimeline from '../components/StoryTimeline'
import { buildMarkers, eventStates, FALLBACK_STORIES } from '../components/storyTypes'
import type { Story, StorySummary } from '../components/storyTypes'

const Globe = lazy(() => import('../Globe'))

type LoadState = { status: 'loading' } | { status: 'error'; code: number | null } | { status: 'success'; story: Story }

const PLAYBACK_MS = 3000
const STORAGE_KEY = 'geo-observatorio:noticia'
const SLUG = /^[\w-]{1,100}$/

const loadErrorMessage = (code: number | null) => code === 404
  ? 'Esta noticia todavía no está disponible en el servidor. Elige otra noticia o inténtalo más tarde.'
  : code === 503
    ? 'La base de datos del servidor no está disponible. Comprueba las migraciones y los datos locales e inténtalo de nuevo.'
    : 'Comprueba que el servidor Django esté iniciado e inténtalo de nuevo.'

// Persistence helpers: storage and history can be unavailable (private mode, sandboxed previews).
const hashSlug = () => {
  try {
    const value = new URLSearchParams(window.location.hash.slice(1)).get('noticia')
    return value && SLUG.test(value) ? value : null
  } catch { return null }
}
const storedSlug = () => {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    return value && SLUG.test(value) ? value : null
  } catch { return null }
}
const rememberSlug = (slug: string) => {
  try { window.localStorage.setItem(STORAGE_KEY, slug) } catch { /* storage unavailable: preference is not kept */ }
}
const reflectInHash = (slug: string) => {
  try {
    if (hashSlug() === slug) return
    // Never rewrite a hash route (`#/…`): the user may have navigated away while the list was loading.
    if (window.location.hash.startsWith('#/') && window.location.hash !== '#/') return
    window.history.replaceState(window.history.state, '', `#noticia=${encodeURIComponent(slug)}`)
  } catch { /* history unavailable: the URL simply does not reflect the story */ }
}
/** Priority: URL hash, last remembered story, first `conflict`, first story. Only slugs in the list are accepted. */
const pickInitialSlug = (stories: StorySummary[]) => {
  const known = (slug: string | null) => slug !== null && stories.some((item) => item.slug === slug)
  const fromHash = hashSlug()
  if (known(fromHash)) return fromHash!
  const fromStorage = storedSlug()
  if (known(fromStorage)) return fromStorage!
  return (stories.find((item) => item.kind === 'conflict') ?? stories[0])?.slug ?? null
}

const REDUCED_MOTION = '(prefers-reduced-motion: reduce)'
const subscribeReducedMotion = (onChange: () => void) => {
  const query = typeof window.matchMedia === 'function' ? window.matchMedia(REDUCED_MOTION) : null
  query?.addEventListener('change', onChange)
  return () => query?.removeEventListener('change', onChange)
}
const prefersReducedMotion = () => typeof window.matchMedia === 'function' && window.matchMedia(REDUCED_MOTION).matches

class GlobeBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    return this.state.failed ? <p className="visual-fallback" role="status">El globo no está disponible. Puedes consultar la noticia y sus fuentes.</p> : this.props.children
  }
}

/** Home: story selector, globe, observation card and timeline (moved unchanged from App.tsx). */
export default function HomePage() {
  const [list, setList] = useState<StoryListState>({ status: 'loading' })
  const [listAttempt, setListAttempt] = useState(0)
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [selected, setSelected] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const [storyId, setStoryId] = useState<string | null>(null)
  // Mirrors storyId for async callbacks (the list effect must not depend on storyId).
  const storyIdRef = useRef<string | null>(null)
  const [showAll, setShowAll] = useState(false)
  const [playing, setPlaying] = useState(false)
  const reducedMotion = useSyncExternalStore(subscribeReducedMotion, prefersReducedMotion, () => false)

  const stories = useMemo(() => list.status === 'success' ? list.stories : list.status === 'error' ? FALLBACK_STORIES : [], [list])

  // Story list. On failure or empty list, the known slugs act as fallback.
  useEffect(() => {
    const controller = new AbortController()
    const settle = (next: StoryListState) => {
      if (controller.signal.aborted) return
      setList(next)
      if (storyIdRef.current) return
      const initial = pickInitialSlug(next.status === 'success' ? next.stories : FALLBACK_STORIES)
      if (!initial) { setState({ status: 'error', code: null }); return }
      storyIdRef.current = initial
      reflectInHash(initial)
      setStoryId(initial)
    }
    fetch('/api/stories/', { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error('API unavailable'); return response.json() })
      .then((data: { stories?: unknown }) => {
        const items = Array.isArray(data.stories)
          ? (data.stories as StorySummary[]).filter((item) => item && typeof item.slug === 'string' && SLUG.test(item.slug) && typeof item.title === 'string')
          : null
        if (items === null) throw new Error('Unexpected response')
        settle(items.length ? { status: 'success', stories: items } : { status: 'error', reason: 'empty' })
      })
      .catch(() => settle({ status: 'error', reason: 'network' }))
    return () => controller.abort()
  }, [listAttempt])

  // Selected story detail.
  useEffect(() => {
    if (!storyId) return
    const controller = new AbortController()
    fetch(`/api/stories/${encodeURIComponent(storyId)}/`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) { const error = new Error('API unavailable') as Error & { code?: number }; error.code = response.status; throw error }
        return response.json()
      })
      .then((story: Story) => {
        if (controller.signal.aborted) return
        if (!story || !Array.isArray(story.events)) throw new Error('Unexpected response')
        setState({ status: 'success', story })
        setSelected(story.events[0]?.id ?? null)
      })
      .catch((error: Error & { code?: number }) => { if (!controller.signal.aborted) setState({ status: 'error', code: error.code ?? null }) })
    return () => controller.abort()
  }, [attempt, storyId])

  const selectStory = (next: string, remember = true) => {
    setPlaying(false)
    if (remember) rememberSlug(next)
    reflectInHash(next)
    if (storyId === next) return
    storyIdRef.current = next
    setState({ status: 'loading' })
    setSelected(null)
    setStoryId(next)
  }

  // Back/forward or a manually edited `#noticia=slug`. Other hashes (#inicio, #claim-…) are ignored.
  useEffect(() => {
    const onHashChange = () => {
      const slug = hashSlug()
      if (!slug || slug === storyId || !stories.some((item) => item.slug === slug)) return
      setPlaying(false)
      rememberSlug(slug)
      storyIdRef.current = slug
      setState({ status: 'loading' })
      setSelected(null)
      setStoryId(slug)
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [storyId, stories])

  const story = state.status === 'success' ? state.story : null
  const events = useMemo(() => story?.events ?? [], [story])
  const activeIndex = events.findIndex((event) => event.id === selected)
  const active = events[activeIndex]
  const states = useMemo(() => eventStates(events, activeIndex), [events, activeIndex])
  const markers = useMemo(() => buildMarkers(events, states, showAll), [events, states, showAll])
  const locatedEvents = events.filter((event) => event.place?.coordinates).length
  const isPlaying = playing && !reducedMotion && events.length > 1

  // Manual selection always stops playback (user interaction wins over auto-advance).
  const chooseEvent = useCallback((id: string) => { setPlaying(false); setSelected(id) }, [])
  const selectRelative = (offset: number) => {
    const next = events[activeIndex + offset]
    if (next) chooseEvent(next.id)
  }
  const togglePlay = () => {
    if (isPlaying) { setPlaying(false); return }
    if (reducedMotion || events.length < 2) return
    if (activeIndex < 0 || activeIndex >= events.length - 1) setSelected(events[0].id)
    setPlaying(true)
  }
  const stopOnInteraction = () => { if (isPlaying) setPlaying(false) }

  // Auto-advance one milestone every PLAYBACK_MS until the end.
  useEffect(() => {
    if (!isPlaying) return
    const timer = window.setTimeout(() => {
      const next = events[activeIndex + 1]
      if (next) setSelected(next.id)
      if (!next || activeIndex + 2 >= events.length) setPlaying(false)
    }, PLAYBACK_MS)
    return () => window.clearTimeout(timer)
  }, [isPlaying, activeIndex, events])

  return (
    <>
      <StorySelector list={list} stories={stories} selectedSlug={storyId} onSelect={(slug) => selectStory(slug)} onRetry={() => { setList({ status: 'loading' }); setListAttempt((value) => value + 1) }} />
      {state.status === 'loading' && <p className="status" role="status">{list.status === 'loading' && !storyId ? 'Cargando noticias…' : 'Cargando la noticia…'}</p>}
      {state.status === 'error' && <div className="status" role="alert"><h1>No pudimos cargar la noticia.</h1><p>{storyId ? loadErrorMessage(state.code) : 'No hay noticias disponibles para mostrar.'}</p><button type="button" className="retry" onClick={() => { setState({ status: 'loading' }); if (storyId) setAttempt((value) => value + 1); else { setList({ status: 'loading' }); setListAttempt((value) => value + 1) } }}>Intentar de nuevo</button></div>}
      {story && <>
        <div className="story-heading"><div><p className="eyebrow">ACTUALIDAD INTERNACIONAL <span> / EN CONTEXTO</span></p><h1>El mundo en perspectiva.</h1></div><p>Hechos, fuentes y análisis <span>·</span> {story.title}</p></div>
        {events.length === 0 ? <p className="status">No hay noticias disponibles todavía.</p> : <>
          <section className="visual-stage" aria-label="Mapa y noticia seleccionada" onPointerDownCapture={stopOnInteraction} onKeyDownCapture={stopOnInteraction}>
            <GlobeBoundary><Suspense fallback={<p className="visual-fallback" role="status">Preparando el globo…</p>}><Globe markers={markers} activeId={active?.id ?? null} onSelect={chooseEvent} /></Suspense></GlobeBoundary>
            {active && <EventCard event={active} index={activeIndex} total={events.length} live={isPlaying ? 'off' : 'polite'} onPrev={() => selectRelative(-1)} onNext={() => selectRelative(1)} />}
          </section>
          <StoryTimeline story={story} states={states} activeIndex={activeIndex} onSelect={chooseEvent} playing={isPlaying} reducedMotion={reducedMotion} onTogglePlay={togglePlay} showAll={showAll} onShowAllChange={setShowAll} visibleMarkers={markers.length} locatedEvents={locatedEvents} />
          <p className="sr-only" aria-live="polite">{isPlaying && active ? `Reproduciendo: hito ${activeIndex + 1} de ${events.length}. ${active.date.label}. ${active.title}` : ''}</p>
        </>}
        <div className="editorial-note"><span aria-hidden="true">✳</span><p><strong>Información en contexto.</strong> {story.summary} Separamos los hechos del análisis. Los marcadores son referencias aproximadas; consulta las fuentes de cada noticia.</p></div>
      </>}
    </>
  )
}
