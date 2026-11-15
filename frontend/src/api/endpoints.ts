// Endpoint functions for CONTRATO_USUARIOS_INGESTA.md §2. Responses are parsed defensively: missing
// optional fields get neutral defaults and wrapped / unwrapped payloads are both accepted where the
// contract does not fix the envelope (profile, submission detail, actions).
import { api, ApiError } from './client'
import type { AgentRun, FetchedDocument, Profile, Submission, SubmissionDetail, User } from './types'
import type { StoryEvent } from '../components/storyTypes'

type Raw = Record<string, unknown>
const isRecord = (value: unknown): value is Raw => Boolean(value) && typeof value === 'object' && !Array.isArray(value)
const str = (value: unknown, fallback = '') => typeof value === 'string' ? value : fallback
const strOrNull = (value: unknown) => typeof value === 'string' && value ? value : null

/** Unexpected payloads are reported as a server error rather than crashing the view. */
const unexpected = () => new ApiError(502, 'La respuesta del servidor no tiene el formato esperado.')

function parseProfile(raw: unknown): Profile {
  const record = isRecord(raw) ? raw : {}
  return {
    display_name: str(record.display_name),
    bio: str(record.bio),
    country: str(record.country),
    organization: str(record.organization),
    language: record.language === 'en' ? 'en' : 'es',
  }
}

export function parseUser(raw: unknown): User {
  if (!isRecord(raw) || typeof raw.username !== 'string') throw unexpected()
  return {
    id: typeof raw.id === 'number' ? raw.id : 0,
    username: raw.username,
    email: str(raw.email),
    is_staff: raw.is_staff === true,
    profile: parseProfile(raw.profile),
  }
}

/** Display name with the username as fallback. */
export const displayName = (user: User) => user.profile.display_name.trim() || user.username

// --- Authentication -------------------------------------------------------------------------

export async function fetchMe(signal?: AbortSignal): Promise<User | null> {
  const { data } = await api.get<unknown>('/api/auth/me/', signal)
  if (!isRecord(data)) throw unexpected()
  return data.authenticated === true ? parseUser(data.user) : null
}

export type RegisterPayload = { username: string; email: string; password: string; display_name: string }

export async function register(payload: RegisterPayload) {
  const { data } = await api.post<unknown>('/api/auth/register/', payload)
  return parseUser(isRecord(data) ? data.user : null)
}

export async function login(username: string, password: string) {
  const { data } = await api.post<unknown>('/api/auth/login/', { username, password })
  return parseUser(isRecord(data) ? data.user : null)
}

export async function logout() {
  await api.post<unknown>('/api/auth/logout/')
}

export async function changePassword(old_password: string, new_password: string) {
  await api.post<unknown>('/api/auth/password/', { old_password, new_password })
}

// --- Profile --------------------------------------------------------------------------------

export type ProfileData = { email: string } & Profile

/** Accepts `{"user": {...}}`, `{"email", "profile": {...}}` or a flat object. */
function parseProfileData(raw: unknown): ProfileData {
  if (!isRecord(raw)) throw unexpected()
  if (isRecord(raw.user)) { const user = parseUser(raw.user); return { email: user.email, ...user.profile } }
  if (isRecord(raw.profile)) return { email: str(raw.email), ...parseProfile(raw.profile) }
  return { email: str(raw.email), ...parseProfile(raw) }
}

export async function fetchProfile(signal?: AbortSignal) {
  const { data } = await api.get<unknown>('/api/profile/', signal)
  return parseProfileData(data)
}

/** PATCH with flat fields (`email` and the profile fields). */
export async function updateProfile(changes: Partial<ProfileData>) {
  const { data } = await api.patch<unknown>('/api/profile/', changes)
  return parseProfileData(data)
}

// --- Submissions ----------------------------------------------------------------------------

function parseSubmission(raw: unknown): Submission {
  if (!isRecord(raw) || typeof raw.id !== 'number') throw unexpected()
  return {
    id: raw.id,
    url: str(raw.url),
    note: str(raw.note),
    status: str(raw.status, 'queued'),
    status_label: str(raw.status_label),
    step_detail: str(raw.step_detail),
    error: str(raw.error),
    created_at: str(raw.created_at),
    updated_at: str(raw.updated_at),
    story_slug: strOrNull(raw.story_slug),
    event_title: strOrNull(raw.event_title),
    submitted_by: strOrNull(raw.submitted_by),
  }
}

const unwrapSubmission = (data: unknown) => isRecord(data) && isRecord(data.submission) ? data.submission : data

function parseDetail(raw: unknown): SubmissionDetail {
  const base = parseSubmission(raw)
  const record = raw as Raw
  const documents: FetchedDocument[] = (Array.isArray(record.documents) ? record.documents : []).filter(isRecord).map((doc) => ({
    title: str(doc.title), url: str(doc.url), publisher: str(doc.publisher), role: str(doc.role),
    published_at: strOrNull(doc.published_at), fetched_at: strOrNull(doc.fetched_at), fetch_error: str(doc.fetch_error),
  }))
  const agent_runs: AgentRun[] = (Array.isArray(record.agent_runs) ? record.agent_runs : []).filter(isRecord).map((run) => ({
    agent: str(run.agent), status: str(run.status), model: str(run.model), finished_at: strOrNull(run.finished_at), error: str(run.error),
  }))
  const preview = isRecord(record.preview) && typeof record.preview.title === 'string' && isRecord(record.preview.date)
    ? { sources: [], evidence_status: '', place: null, description: '', ...record.preview } as unknown as StoryEvent
    : null
  return { ...base, documents, agent_runs, preview, review_note: str(record.review_note) }
}

export type CreateSubmissionPayload = { url: string; note?: string; target_story?: string }

/** 202 -> new submission; 200 -> an active submission with the same normalised URL already existed. */
export async function createSubmission(payload: CreateSubmissionPayload) {
  const { status, data } = await api.post<unknown>('/api/submissions/', payload)
  return { duplicate: status === 200, submission: parseSubmission(unwrapSubmission(data)) }
}

export async function listSubmissions(all = false, signal?: AbortSignal) {
  const { data } = await api.get<unknown>(all ? '/api/submissions/?all=1' : '/api/submissions/', signal)
  if (!isRecord(data) || !Array.isArray(data.submissions)) throw unexpected()
  return data.submissions.map(parseSubmission)
}

export async function fetchSubmission(id: number, signal?: AbortSignal) {
  const { data } = await api.get<unknown>(`/api/submissions/${id}/`, signal)
  return parseDetail(unwrapSubmission(data))
}

export const retrySubmission = (id: number) => api.post<unknown>(`/api/submissions/${id}/retry/`)
export const publishSubmission = (id: number, note: string) => api.post<unknown>(`/api/submissions/${id}/publish/`, note ? { note } : {})
export const rejectSubmission = (id: number, note: string) => api.post<unknown>(`/api/submissions/${id}/reject/`, { note })
