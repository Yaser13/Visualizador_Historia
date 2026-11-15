// Display helpers for dates, hosts and submission statuses.
import { formatDate } from './storyTypes'

const DATE_TIME = new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short' })

/** ISO date (`YYYY-MM-DD`) -> dd/mm/yyyy; ISO date-time -> localised date and time; otherwise null. */
export function formatDateTime(value?: string | null) {
  if (!value) return null
  const dateOnly = formatDate(value)
  if (dateOnly) return dateOnly
  const time = Date.parse(value)
  return Number.isNaN(time) ? null : DATE_TIME.format(time)
}

export function hostOf(url: string) {
  try { return new URL(url).hostname.replace(/^www\./, '') } catch { return url }
}

/** Spanish labels for `NewsSubmission.status`; the server `status_label` takes precedence when present. */
export const STATUS_LABELS: Record<string, string> = {
  queued: 'En cola',
  fetching: 'Descargando la noticia',
  researching: 'Buscando cobertura relacionada',
  extracting: 'Extrayendo afirmaciones',
  verifying: 'Verificando citas',
  geolocating: 'Ubicando lugares',
  analyzing: 'Redactando el análisis',
  review: 'Pendiente de revisión',
  published: 'Publicada',
  rejected: 'Rechazada',
  failed: 'Error',
}

export const statusLabel = (status: string, serverLabel?: string) => serverLabel || STATUS_LABELS[status] || status

/** Visual tone of a status badge (the text always carries the meaning, not only the colour). */
export const statusTone = (status: string) => ({ queued: 'queued', review: 'review', published: 'published', rejected: 'rejected', failed: 'failed' }[status] ?? 'progress')

/** `submitted_by` of a public event: the contract exposes only the display name (string or `{display_name}`). */
export const submitterName = (value: unknown) => typeof value === 'string'
  ? value
  : value && typeof value === 'object' && typeof (value as { display_name?: unknown }).display_name === 'string'
    ? (value as { display_name: string }).display_name
    : null

export const AGENT_LABELS: Record<string, string> = {
  researcher: 'Investigador (búsqueda de cobertura)',
  extractor: 'Extractor de afirmaciones',
  verifier: 'Verificador de citas',
  geolocator: 'Geolocalizador',
  analyst: 'Analista',
}
