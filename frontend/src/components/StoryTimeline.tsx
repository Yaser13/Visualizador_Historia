import { useId, useRef } from 'react'
import type { KeyboardEvent } from 'react'
import { CategoryIcon } from '../icons'
import { categoryMeta } from '../categories'
import { formatDate, positionInRange, timelineRange } from './storyTypes'
import type { EventState, Story } from './storyTypes'

type Props = {
  story: Story
  states: EventState[]
  activeIndex: number
  onSelect: (id: string) => void
  playing: boolean
  reducedMotion: boolean
  onTogglePlay: () => void
  showAll: boolean
  onShowAllChange: (showAll: boolean) => void
  visibleMarkers: number
  locatedEvents: number
}

/**
 * Story timeline: playback and display controls, proportional date bar, accessible list of
 * milestones (roving tabindex + arrow keys) and the legend of the icons present in the story.
 */
export default function StoryTimeline({ story, states, activeIndex, onSelect, playing, reducedMotion, onTogglePlay, showAll, onShowAllChange, visibleMarkers, locatedEvents }: Props) {
  const buttons = useRef(new Map<string, HTMLButtonElement>())
  const hintId = useId()
  const modeName = useId()
  const events = story.events
  const active = events[activeIndex]
  const range = timelineRange(story)
  const activePosition = range && active ? positionInRange(active.date.start, range) : null
  const categories = [...new Set(events.map((event) => categoryMeta(event.category).key))]
  const asOf = formatDate(story.as_of)
  const atEnd = activeIndex >= events.length - 1
  const focusIndex = activeIndex >= 0 ? activeIndex : 0

  const move = (index: number, focus = true) => {
    const target = events[Math.min(events.length - 1, Math.max(0, index))]
    if (!target) return
    onSelect(target.id)
    if (focus) buttons.current.get(target.id)?.focus()
  }
  const onKeyDown = (event: KeyboardEvent<HTMLOListElement>) => {
    const offsets: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }
    if (event.key in offsets) move(focusIndex + offsets[event.key])
    else if (event.key === 'Home') move(0)
    else if (event.key === 'End') move(events.length - 1)
    else return
    event.preventDefault()
  }

  return (
    <section className="timeline" aria-label="Línea de tiempo de la noticia">
      <div className="timeline-heading">
        <div><p className="eyebrow">EVOLUCIÓN DE LA NOTICIA</p><h2>Línea de tiempo</h2></div>
        <p className="timeline-meta">
          <span>{events.length} {events.length === 1 ? 'hito' : 'hitos'}</span>
          {asOf && <span>Última verificación: {asOf}</span>}
        </p>
      </div>

      <div className="timeline-toolbar">
        <div className="playback">
          <button type="button" className="play-button" onClick={onTogglePlay} disabled={reducedMotion || events.length < 2} aria-describedby={reducedMotion ? `${hintId}-motion` : undefined}>
            <span aria-hidden="true">{playing ? '❚❚' : '▶'}</span> {playing ? 'Pausar' : atEnd && events.length > 1 ?'Reproducir evolución desde el inicio' : 'Reproducir evolución'}
          </button>
          <button type="button" className="step-button" onClick={() => move(activeIndex - 1, false)} disabled={activeIndex <= 0} aria-label="Hito anterior">←</button>
          <button type="button" className="step-button" onClick={() => move(activeIndex + 1, false)} disabled={atEnd} aria-label="Hito siguiente">→</button>
        </div>
        <fieldset className="display-mode">
          <legend>Mostrar en el globo:</legend>
          <label><input type="radio" name={modeName} checked={!showAll} onChange={() => onShowAllChange(false)} /> hasta la fecha seleccionada</label>
          <label><input type="radio" name={modeName} checked={showAll} onChange={() => onShowAllChange(true)} /> toda la cronología</label>
        </fieldset>
      </div>
      {reducedMotion && <p className="timeline-hint" id={`${hintId}-motion`}>Reproducción automática desactivada por tu preferencia de movimiento reducido. Avanza paso a paso con las flechas.</p>}
      <p className="timeline-hint">
        {visibleMarkers} de {locatedEvents} {locatedEvents === 1 ? 'ubicación visible' : 'ubicaciones visibles'} en el globo
        {locatedEvents < events.length && <> · {events.length - locatedEvents} {events.length - locatedEvents === 1 ? 'hito sin ubicación puntual' : 'hitos sin ubicación puntual'}</>}.
      </p>

      {range && (
        <div className="timeline-track" role="img" aria-label={`Progreso de la cronología entre ${formatDate(range.startIso)} y ${formatDate(range.endIso)}${active ? `: hito ${activeIndex + 1} de ${events.length}, ${active.date.label}` : ''}.`}>
          <div className="track-line">
            {activePosition !== null && <span className="track-fill" style={{ width: `${activePosition}%` }} />}
            {events.map((event, index) => {
              const position = positionInRange(event.date.start, range)
              if (position === null) return null
              return <span key={event.id} className={`track-node is-${states[index]}`} style={{ left: `${position}%`, borderColor: categoryMeta(event.category).color }} title={`${event.date.label} · ${event.title}`} />
            })}
          </div>
          <div className="track-labels"><span>{formatDate(range.startIso)}</span><span>{formatDate(range.endIso)}</span></div>
        </div>
      )}

      <p className="sr-only" id={hintId}>Usa las flechas izquierda y derecha para moverte entre hitos; Inicio y Fin para ir al primero o al último.</p>
      <ol aria-label="Hitos de la noticia" aria-describedby={hintId} onKeyDown={onKeyDown}>
        {events.map((event, index) => {
          const meta = categoryMeta(event.category)
          const state = states[index]
          return (
            <li key={event.id} className={state === 'future' ? 'is-future' : undefined}>
              <button
                type="button"
                ref={(node) => { if (node) buttons.current.set(event.id, node); else buttons.current.delete(event.id) }}
                className={state === 'active' ? 'event selected' : 'event'}
                tabIndex={index === focusIndex ? 0 : -1}
                aria-current={state === 'active' ? 'step' : undefined}
                onClick={() => onSelect(event.id)}
              >
                <span className="timeline-node" aria-hidden="true" />
                <span className="timeline-date">{event.date.label}</span>
                <span className="timeline-title"><span className="timeline-icon"><CategoryIcon category={event.category} size={18} /></span> {event.title}</span>
                <span className="timeline-number">{String(index + 1).padStart(2, '0')} · {meta.label}{state === 'future' && <span className="sr-only"> · posterior al hito seleccionado</span>}</span>
              </button>
            </li>
          )
        })}
      </ol>

      <div className="icon-legend">
        <ul aria-label="Leyenda de iconos">
          {categories.map((key) => <li key={key}><CategoryIcon category={key} size={16} /> {categoryMeta(key).label}</li>)}
        </ul>
        <p className="timeline-legend">Los iconos indican el tipo de acontecimiento; no representan fuerzas, armas, frentes ni control territorial.</p>
        <p className="timeline-legend">Cronología actualizable: se añaden hitos cuando hay nuevas fuentes verificadas.</p>
      </div>
    </section>
  )
}
