import { CategoryIcon } from '../icons'
import { kindCategory } from './storyTypes'
import type { StorySummary } from './storyTypes'

export type StoryListState =
  | { status: 'loading' }
  | { status: 'success'; stories: StorySummary[] }
  | { status: 'error'; reason: 'network' | 'empty' }

type Props = {
  list: StoryListState
  stories: StorySummary[]
  selectedSlug: string | null
  onSelect: (slug: string) => void
  onRetry: () => void
}

/** Story picker fed by `GET /api/stories/`, with the known slugs as fallback when it fails. */
export default function StorySelector({ list, stories, selectedSlug, onSelect, onRetry }: Props) {
  return (
    <nav className="story-selector" aria-label="Seleccionar noticia" aria-busy={list.status === 'loading'}>
      <span>EXPLORAR NOTICIAS</span>
      {list.status === 'loading' && <p className="selector-status" role="status">Cargando noticias…</p>}
      {stories.map((item) => {
        const count = typeof item.events_count === 'number' ? item.events_count : null
        return (
          <button type="button" key={item.slug} aria-pressed={selectedSlug === item.slug} onClick={() => onSelect(item.slug)}>
            <CategoryIcon category={kindCategory(item.kind)} size={16} />
            <span className="selector-title">{item.title}</span>
            {count !== null && <span className="selector-count">{count} {count === 1 ? 'hito' : 'hitos'}</span>}
          </button>
        )
      })}
      {list.status === 'error' && (
        <p className="selector-status selector-error" role="alert">
          {list.reason === 'empty' ? 'El listado de noticias está vacío.' : 'No pudimos cargar el listado de noticias.'} Se muestran las noticias conocidas.
          <button type="button" className="selector-retry" onClick={onRetry}>Reintentar listado</button>
        </p>
      )}
    </nav>
  )
}
