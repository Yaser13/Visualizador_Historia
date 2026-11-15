// Types for the users / submissions API (docs/api/CONTRATO_USUARIOS_INGESTA.md §2).
// The endpoints are agreed but may not be implemented yet: parsing in `endpoints.ts` is tolerant.
import type { StoryEvent } from '../components/storyTypes'

export type Language = 'es' | 'en'

export type Profile = {
  display_name: string
  bio: string
  country: string
  organization: string
  language: Language
}

export type User = {
  id: number
  username: string
  email: string
  is_staff: boolean
  profile: Profile
}

export const SUBMISSION_STATUSES = [
  'queued', 'fetching', 'researching', 'extracting', 'verifying', 'geolocating', 'analyzing', 'review', 'published', 'rejected', 'failed',
] as const
export type SubmissionStatus = typeof SUBMISSION_STATUSES[number]

/** Item of `GET /api/submissions/`. */
export type Submission = {
  id: number
  url: string
  note: string
  status: SubmissionStatus | string
  status_label: string
  step_detail: string
  error: string
  created_at: string
  updated_at: string
  story_slug: string | null
  event_title: string | null
  /** `display_name` of the submitter. */
  submitted_by: string | null
}

export type FetchedDocument = {
  title: string
  url: string
  publisher: string
  role: 'submitted' | 'related' | string
  published_at: string | null
  fetched_at: string | null
  fetch_error: string
}

export type AgentRun = {
  agent: string
  status: 'ok' | 'error' | 'skipped' | string
  model: string
  finished_at: string | null
  error: string
}

/** `GET /api/submissions/<id>/`. `preview` is the draft event (same shape as a story event). */
export type SubmissionDetail = Submission & {
  documents: FetchedDocument[]
  agent_runs: AgentRun[]
  preview: StoryEvent | null
  review_note: string
}

/** Pipeline statuses after which polling stops (the pipeline no longer advances on its own). */
export const TERMINAL_STATUSES: ReadonlySet<string> = new Set(['review', 'published', 'rejected', 'failed'])
