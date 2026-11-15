// Types for the stories API (docs/api/CONTRATO_CRONOLOGIAS.md §2) and pure helpers shared by App,
// the story selector and the timeline. Every field added by the v1 contract is optional so that
// legacy stories (`expansion-de-roma`, `geopolitica`) keep working.
import type { GlobeMarker } from '../Globe'

export type Source = {
  title: string
  creator: string
  publication: string
  url: string
  locator: string
  rights_note: string
  published_at?: string | null
  /** Literal quote from the stored document (contract CONTRATO_USUARIOS_INGESTA.md §0), when provided. */
  excerpt?: string
}
/** `editorial` (default) or `ai_pipeline` (observation generated from a user submission). */
export type Origin = 'editorial' | 'ai_pipeline' | (string & {})
export type Claim = { id: number; text: string; kind: string; status: string; attributed_to: string | null; sources: Source[] }
export type Actor = { name: string; kind: string; role: string; note: string; claim_id?: number }
export type Effect = { description: string; affected_actor: string | null; perspective: string | null; valence: string; claim_id?: number }
export type EventDate = {
  label: string
  /** ISO `YYYY-MM-DD` or null (contract v1). */
  start?: string | null
  end?: string | null
  precision?: string
  start_year?: number | null
  end_year?: number | null
}
export type Place = { label: string; note: string; coordinates: [number, number] | null; coordinate_source: { url: string; locator: string } | null }
export type StoryEvent = {
  id: string
  order: number
  title: string
  description: string
  category?: string
  analysis?: string
  published_at?: string
  as_of?: string
  date: EventDate
  place: Place | null
  evidence_status: string
  sources: Source[]
  claims?: Claim[]
  actors?: Actor[]
  effects?: Effect[]
  origin?: Origin
  /** Display name of the submitter (contract §1); never email or username. */
  submitted_by?: string | { display_name?: string } | null
}
export type Story = {
  slug?: string
  title: string
  summary: string
  kind?: string
  as_of?: string | null
  first_event_date?: string | null
  last_event_date?: string | null
  origin?: Origin
  events: StoryEvent[]
}
/** Item of `GET /api/stories/`. */
export type StorySummary = {
  slug: string
  title: string
  summary?: string
  kind?: string
  events_count?: number
  first_event_date?: string | null
  last_event_date?: string | null
  as_of?: string | null
  origin?: Origin
}

/** Used only when `GET /api/stories/` fails or is empty; titles are UI labels, not data. */
export const FALLBACK_STORIES: StorySummary[] = [
  { slug: 'guerra-sudan', title: 'Guerra en Sudán', kind: 'conflict' },
  { slug: 'conflicto-armado', title: 'Conflicto armado', kind: 'conflict' },
  { slug: 'geopolitica', title: 'Clima y diplomacia', kind: 'diplomacy' },
]

/** Story kind -> icon category from icons.tsx. Unknown kinds fall back to the generic icon. */
export const kindCategory = (kind?: string) => ({
  conflict: 'conflicto', diplomacy: 'negociacion', humanitarian: 'humanitario', politics: 'politica', climate: 'clima', agreement: 'acuerdo',
}[kind ?? ''] ?? null)

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

export const formatDate = (value?: string | null) => {
  if (!value || !ISO_DATE.test(value)) return null
  const [year, month, day] = value.split('-')
  return `${day}/${month}/${year}`
}

/** Days since the epoch for an ISO date, or null when missing/invalid. */
export const isoDay = (value?: string | null) => {
  if (!value || !ISO_DATE.test(value)) return null
  const [year, month, day] = value.split('-').map(Number)
  const time = Date.UTC(year, month - 1, day)
  return Number.isNaN(time) ? null : time / 86_400_000
}

export type EventState = GlobeMarker['state']

/**
 * Position of each event relative to the selected one. Compares `date.start` when both events
 * have it (ties broken by list order); otherwise uses list order. Without a selection, all are past.
 */
export function eventStates(events: StoryEvent[], activeIndex: number): EventState[] {
  const active = events[activeIndex]
  const activeDay = isoDay(active?.date.start)
  return events.map((event, index) => {
    if (!active) return 'past'
    if (index === activeIndex) return 'active'
    const day = isoDay(event.date.start)
    if (day !== null && activeDay !== null && day !== activeDay) return day < activeDay ? 'past' : 'future'
    return index < activeIndex ? 'past' : 'future'
  })
}

/** Markers for events with coordinates; `future` ones are dropped unless `includeFuture`. */
export function buildMarkers(events: StoryEvent[], states: EventState[], includeFuture: boolean): GlobeMarker[] {
  const markers: GlobeMarker[] = []
  events.forEach((event, index) => {
    const coordinates = event.place?.coordinates
    const state = states[index]
    if (!coordinates || (state === 'future' && !includeFuture)) return
    markers.push({
      id: event.id,
      coordinates,
      category: event.category ?? '',
      label: event.place?.label ?? '',
      title: event.title,
      dateLabel: event.date.label,
      state,
    })
  })
  return markers
}

/** Range for the progress bar: story-level dates, else the min/max `date.start` of the events. */
export function timelineRange(story: Story): { start: number; end: number; startIso: string; endIso: string } | null {
  const dated = story.events.map((event) => event.date.start).filter((value): value is string => isoDay(value) !== null).sort()
  const startIso = isoDay(story.first_event_date) !== null ? story.first_event_date! : dated[0]
  const endIso = isoDay(story.last_event_date) !== null ? story.last_event_date! : dated[dated.length - 1]
  const start = isoDay(startIso)
  const end = isoDay(endIso)
  if (start === null || end === null || end < start) return null
  return { start, end, startIso, endIso }
}

/** Percentage (0-100) of a date inside the range; 50 when the range has no length; null if undated. */
export function positionInRange(value: string | null | undefined, range: { start: number; end: number }) {
  const day = isoDay(value)
  if (day === null) return null
  if (range.end === range.start) return 50
  return Math.min(100, Math.max(0, ((day - range.start) / (range.end - range.start)) * 100))
}
