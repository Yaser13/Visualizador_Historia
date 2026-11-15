import { Component, lazy, Suspense, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
const Globe = lazy(() => import('./Globe'))
import './App.css'

type Source = { title: string; creator: string; publication: string; url: string; locator: string; rights_note: string }
type Event = { id: string; order: number; title: string; description: string; date: { label: string }; place: { label: string; note: string } | null; evidence_status: string; sources: Source[] }
type Story = { title: string; summary: string; events: Event[] }
type LoadState = { status: 'loading' } | { status: 'error' } | { status: 'success'; story: Story }

class GlobeBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    return this.state.failed ? <p className="status" role="status">El globo no está disponible. Puedes explorar la cronología y sus fuentes.</p> : this.props.children
  }
}

function App() {
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [selected, setSelected] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/stories/expansion-de-roma/', { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error('API unavailable'); return response.json() })
      .then((story: Story) => { setState({ status: 'success', story }); setSelected(story.events[0]?.id ?? null) })
      .catch(() => { if (!controller.signal.aborted) setState({ status: 'error' }) })
    return () => controller.abort()
  }, [attempt])

  const story = state.status === 'success' ? state.story : null
  const active = story?.events.find((event) => event.id === selected)
  return (
    <div className="shell">
      <header className="topbar"><a href="#inicio" className="brand"><span className="brand-icon" aria-hidden="true">✳</span> HISTORICAL EARTH</a><span className="edition">UN ATLAS PARA EXPLORAR EL PASADO</span><span className="edition-number">ESTUDIO 01 / ROMA</span></header>
      <main id="inicio">
        <section className="intro"><div><p className="eyebrow">HISTORIAS QUE DAN FORMA AL MUNDO <span> / 01</span></p><h1>La expansión<br /><em>de Roma.</em></h1><p className="intro-copy">Una historia de conquistas, diplomacia y transformación. Explora los acontecimientos que cambiaron el Mediterráneo.</p></div><div className="intro-side"><span>509—27 A. E. C.</span><p>DE LA REPÚBLICA<br />AL PRINCIPADO</p></div></section>
        <div className="notice"><span aria-hidden="true">✳</span><p><strong>Una historia en construcción.</strong> Los acontecimientos y sus ubicaciones están en revisión. Las fuentes están disponibles en cada detalle.</p></div>
        {state.status === 'loading' && <p className="status" role="status">Cargando la historia…</p>}
        {state.status === 'error' && <div className="status" role="alert"><p>No se pudo cargar la historia. Comprueba que el servidor Django esté iniciado.</p><button className="retry" onClick={() => { setState({ status: 'loading' }); setAttempt(attempt + 1) }}>Intentar de nuevo</button></div>}
        {story && <GlobeBoundary><Suspense fallback={<p className="status" role="status">Cargando el globo…</p>}><Globe /></Suspense></GlobeBoundary>}
        {story && <section className="workspace" aria-label="Explorar la historia"><div className="timeline"><div className="section-heading"><div><p className="eyebrow">EL RECORRIDO</p><h2>Una historia en el tiempo</h2></div><span>{String(story.events.length).padStart(2, '0')} HITOS</span></div><p className="hint">Selecciona un acontecimiento para conocer más.</p>{story.events.length === 0 ? <p>No hay acontecimientos disponibles todavía.</p> : <ol>{story.events.map((event, index) => <li key={event.id}><button className={event.id === selected ? 'event selected' : 'event'} onClick={() => setSelected(event.id)} aria-pressed={event.id === selected}><span className="event-number">{String(index + 1).padStart(2, '0')}</span><span className="event-content"><span className="event-date">{event.date.label}</span><span className="event-title">{event.title}</span></span><span className="event-arrow" aria-hidden="true">↗</span></button></li>)}</ol>}</div>
        <aside className="detail" aria-label="Detalle del acontecimiento">{active && <><div className="detail-top"><span>ACONTECIMIENTO {String(active.order).padStart(2, '0')}</span><span>EN REVISIÓN</span></div><div className="detail-body"><p className="detail-date">{active.date.label}</p><h2>{active.title}</h2><p className="description">{active.description}</p><div className="detail-rule"/><p className="detail-label">LUGAR DE REFERENCIA</p><p className="place">{active.place?.label ?? 'Ubicación desconocida'}</p><p className="place-note">{active.place?.note ?? 'No hay información geográfica disponible.'}</p><div className="detail-rule"/><p className="detail-label">FUENTE DOCUMENTAL</p>{active.sources.map((source) => <div className="source" key={source.url + source.locator}><a href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a><p>{source.creator} · {source.publication}</p><p>{source.locator}</p></div>)}</div><div className="detail-footer"><span>HISTORICAL EARTH</span><span>FUENTES Y CONTEXTO / 01</span></div></>}</aside></section>}
        <footer><span>HISTORICAL EARTH ©</span><span>EL PASADO, EN PERSPECTIVA.</span><span>UN PROYECTO EN EVOLUCIÓN ↗</span></footer>
      </main>
    </div>
  )
}
export default App


