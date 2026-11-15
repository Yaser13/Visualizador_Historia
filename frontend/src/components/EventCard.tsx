import type { MouseEvent } from 'react'
import { CategoryIcon } from '../icons'
import { categoryMeta } from '../categories'
import { AiBadge } from './Badges'
import { submitterName } from './format'
import { formatDate } from './storyTypes'
import type { Source, StoryEvent } from './storyTypes'

const claimKind = (value: string) => ({ fact: 'Hecho', statement: 'Declaración', analysis: 'Análisis', objective: 'Objetivo declarado', action: 'Acción' }[value] ?? value)
const claimStatus = (value: string) => ({ supported: 'Respaldada', disputed: 'Disputada', uncertain: 'Incierta', draft: 'En revisión', rejected: 'Rechazada' }[value] ?? value)
const actorRole = (value: string) => ({ participant: 'Participante', host: 'Anfitrión', declared_initiator: 'Iniciador declarado', affected: 'Afectado', other: 'Otro' }[value] ?? value)
const effectValence = (value: string) => ({ positive: 'Positiva', negative: 'Negativa', mixed: 'Mixta', unknown: 'Sin valoración determinada' }[value] ?? value)
const sourcePublication = (source: Source) => {
  const publication = source.publication ?? ''
  const creator = source.creator ?? ''
  return creator && publication.includes(creator) ? publication : [creator, publication].filter(Boolean).join(' · ')
}

type Props = {
  event: StoryEvent
  index: number
  total: number
  /** `aria-live` of the body (off during playback). */
  live?: 'off' | 'polite'
  onPrev?: () => void
  onNext?: () => void
  /** Draft preview of a submission (changes the AI notice wording). */
  draft?: boolean
  /**
   * Home page: `#claim-…` links change the hash as before. Elsewhere (hash routes) changing the hash
   * would leave the page, so the link scrolls to the claim without navigating.
   */
  inPageAnchors?: boolean
  className?: string
}

/** Observation card shared by the home page and the submission draft preview. */
export default function EventCard({ event: active, index, total, live = 'polite', onPrev, onNext, draft = false, inPageAnchors = true, className = 'event-card' }: Props) {
  const activeMeta = categoryMeta(active.category)
  const isAi = active.origin === 'ai_pipeline'
  // Without `place` the event is regional or has no single documented place (QA GEO-14 D3); a place
  // without coordinates keeps its own label and note.
  const placeNote = active.place ? active.place.note : 'Acontecimiento regional o sin un lugar único documentado; el globo muestra una vista general.'

  const followClaim = (click: MouseEvent<HTMLAnchorElement>, claimId: number) => {
    const claim = document.getElementById(`claim-${claimId}`)
    if (!claim) { click.preventDefault(); return }
    claim.closest('details')?.setAttribute('open', '')
    if (!inPageAnchors) {
      click.preventDefault()
      claim.scrollIntoView({ block: 'start' })
    }
  }

  return (
    <article className={className} aria-labelledby="event-title">
      <div className="card-topline"><span className="card-category"><CategoryIcon category={active.category} size={14} /> {activeMeta.label.toUpperCase()}</span><span>{String(index + 1).padStart(2, '0')} / {String(total).padStart(2, '0')}</span></div>
      {isAi && <AiBadge submittedBy={submitterName(active.submitted_by)} draft={draft} />}
      <div className="card-body" aria-live={live}>
        <p className="event-date">FECHA DEL ACONTECIMIENTO · {active.date.label}</p>
        <h2 id="event-title">{active.title}</h2>
        <p className="section-label">LO QUE SABEMOS</p><p className="description">{active.description}</p>
        {active.claims?.filter((claim) => claim.kind === 'statement').map((claim) => <div key={claim.id}><p className="section-label analysis-label">DECLARACIÓN {claim.attributed_to ? `· ${claim.attributed_to}` : '· ATRIBUCIÓN NO DISPONIBLE'}</p><p className="description">{claim.text}</p></div>)}
        {active.claims?.filter((claim) => claim.kind === 'analysis').map((claim) => <div key={claim.id}><p className="section-label analysis-label">ANÁLISIS GEOPOLÍTICO{claim.attributed_to ? ` · ${claim.attributed_to}` : ''}</p><p className="description">{claim.text}</p></div>)}
        {active.analysis && !active.claims && <><p className="section-label analysis-label">ANÁLISIS GEOPOLÍTICO</p><p className="description">{active.analysis}</p></>}
        <div className="place-row"><span className="place-symbol" aria-hidden="true"><CategoryIcon category={active.category} size={22} /></span><div><span className="micro-label">LUGAR DE REFERENCIA</span><p>{active.place ? active.place.label || 'Sin ubicación puntual' : 'Sin ubicación puntual'}</p></div></div>
        {placeNote && <p className="place-note">{placeNote}</p>}
        {(active.as_of || active.published_at) && <p className="place-note">{active.published_at && <>Publicación: {formatDate(active.published_at) ?? active.published_at}. </>}{active.as_of && <>Última verificación: {formatDate(active.as_of) ?? active.as_of}.</>}</p>}
      </div>
      {active.claims && <details className="sources"><summary>Afirmaciones y evidencia <span aria-hidden="true">↗</span></summary><div className="sources-body"><p>El estado «respaldada» refleja la evidencia registrada, no certeza absoluta.</p>{active.claims.length ? active.claims.map((claim) => <section className="evidence-item" id={`claim-${claim.id}`} key={claim.id}><p className="evidence-label">{claimKind(claim.kind)} · {claimStatus(claim.status)}</p><p>{claim.text}</p>{claim.attributed_to && <p>Atribuido a: {claim.attributed_to}</p>}{claim.sources?.length ? <ul>{claim.sources.map((source, sourceIndex) => <li key={`${source.url}-${source.locator}-${sourceIndex}`}><a href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a> · {source.locator}{source.excerpt && <blockquote className="evidence-quote"><span className="sr-only">Cita literal de la fuente: </span>«{source.excerpt}»</blockquote>}</li>)}</ul> : <p>Fuente no disponible.</p>}</section>) : <p>No hay afirmaciones disponibles.</p>}</div></details>}
      {active.actors && <details className="sources"><summary>Actores y sus papeles <span aria-hidden="true">↗</span></summary><div className="sources-body">{active.actors.length ? <ul>{active.actors.map((actor, actorIndex) => <li className="evidence-item" key={`${actor.name}-${actor.role}-${actorIndex}`}><strong>{actor.name}</strong> · {actorRole(actor.role)}{actor.note && <p>{actor.note}</p>}{actor.claim_id && <p><a href={`#claim-${actor.claim_id}`} onClick={(click) => followClaim(click, actor.claim_id!)}>Ver afirmación vinculada</a></p>}</li>)}</ul> : <p>No hay actores documentados.</p>}</div></details>}
      {active.effects && <details className="sources"><summary>Efectos y perspectivas <span aria-hidden="true">↗</span></summary><div className="sources-body">{active.effects.length ? <ul>{active.effects.map((effect, effectIndex) => <li className="evidence-item" key={`${effect.description}-${effectIndex}`}><p>{effect.description}</p>{effect.affected_actor && <p>Actor afectado: {effect.affected_actor}</p>}{effect.perspective && <p>Perspectiva: {effect.perspective}</p>}<p>Valoración: {effectValence(effect.valence)}</p>{effect.claim_id && <p><a href={`#claim-${effect.claim_id}`} onClick={(click) => followClaim(click, effect.claim_id!)}>Ver afirmación vinculada</a></p>}</li>)}</ul> : <p>No hay efectos documentados con evidencia suficiente.</p>}</div></details>}
      <details className="sources"><summary>Fuentes y precisión <span aria-hidden="true">↗</span></summary><div className="sources-body"><p>Los hechos proceden de las fuentes enlazadas; el análisis es una interpretación y puede cambiar con nueva información.</p>{(active.sources ?? []).map((source) => <div className="source" key={source.url + source.locator}><a href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a><p>{sourcePublication(source)}</p><p>{source.locator}</p></div>)}{active.place?.coordinate_source && <p><a href={active.place.coordinate_source.url} target="_blank" rel="noreferrer">Fuente de la ubicación ↗</a> · {active.place.coordinate_source.locator}</p>}</div></details>
      {total > 1 && onPrev && onNext && <div className="card-navigation"><span>EXPLORAR HITOS</span><div><button type="button" onClick={onPrev} disabled={index <= 0} aria-label="Hito anterior">←</button><button type="button" onClick={onNext} disabled={index >= total - 1} aria-label="Hito siguiente">→</button></div></div>}
    </article>
  )
}
