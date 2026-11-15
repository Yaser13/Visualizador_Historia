// Minimal JSON client for the Django API (session cookie + CSRF), contract CONTRATO_USUARIOS_INGESTA.md §2 and §4.
// - Same-origin requests with the session cookie (`credentials: 'same-origin'`; Vite proxies /api in dev).
// - `GET /api/auth/csrf/` is requested at start-up; unsafe methods send `X-CSRFToken`, read from the
//   `csrftoken` cookie on every request (Django rotates it on login), with the value returned in the
//   body as fallback when the cookie cannot be read.
// - Errors are normalised into `ApiError` (`detail`, `errors` per field, HTTP status).
// No credentials or tokens are stored in localStorage.

const UNSAFE = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])
const NON_FIELD_KEYS = ['__all__', 'non_field_errors']

export type FieldErrors = Record<string, string[]>

const DEFAULT_MESSAGES: Record<number, string> = {
  0: 'No pudimos conectar con el servidor. Comprueba tu conexión e inténtalo de nuevo.',
  400: 'Revisa los datos del formulario.',
  401: 'Necesitas iniciar sesión para continuar.',
  403: 'No tienes permiso para realizar esta acción.',
  404: 'No encontramos lo que buscas o no tienes acceso a ello.',
  409: 'La operación entra en conflicto con el estado actual. Recarga e inténtalo de nuevo.',
  429: 'Has alcanzado el límite de solicitudes. Inténtalo más tarde.',
  503: 'El servicio no está disponible en este momento. Inténtalo más tarde.',
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: string | null
  /** Field errors (`{"errors": {"campo": ["mensaje"]}}`), without the non-field keys. */
  readonly errors: FieldErrors
  /** Errors not tied to a field (`__all__`, `non_field_errors`). */
  readonly general: string[]

  constructor(status: number, detail: string | null = null, errors: FieldErrors = {}, general: string[] = []) {
    super(detail ?? defaultMessage(status))
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.errors = errors
    this.general = general
  }

  /** Message suitable for the UI: the server `detail` when present, else a generic one by status. */
  get userMessage() {
    return this.detail || this.general[0] || defaultMessage(this.status)
  }
  get isNetwork() { return this.status === 0 }
  get hasFieldErrors() { return Object.keys(this.errors).length > 0 }
}

export function defaultMessage(status: number) {
  return DEFAULT_MESSAGES[status] ?? (status >= 500 ? 'El servidor tuvo un problema. Inténtalo de nuevo en unos minutos.' : 'No pudimos completar la operación.')
}

export const isAbort = (error: unknown) => error instanceof DOMException && error.name === 'AbortError'

/** Any error -> ApiError (network failures become status 0). Abort errors must be filtered by callers first. */
export const toApiError = (error: unknown) => error instanceof ApiError ? error : new ApiError(0)

function readCookie(name: string) {
  try {
    const match = document.cookie.split(';').map((part) => part.trim()).find((part) => part.startsWith(`${name}=`))
    return match ? decodeURIComponent(match.slice(name.length + 1)) : null
  } catch { return null }
}

let csrfFromBody: string | null = null
let csrfRequest: Promise<void> | null = null

/** Requests `/api/auth/csrf/` (once, unless `force`) so Django sets the `csrftoken` cookie. Never throws. */
export function ensureCsrf(force = false): Promise<void> {
  if (!csrfRequest || force) {
    csrfRequest = fetch('/api/auth/csrf/', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(async (response) => {
        if (!response.ok) throw new Error('csrf unavailable')
        const data = await response.json().catch(() => null) as { csrfToken?: unknown } | null
        if (data && typeof data.csrfToken === 'string') csrfFromBody = data.csrfToken
      })
      .catch(() => { csrfRequest = null })
  }
  return csrfRequest
}

const csrfToken = () => readCookie('csrftoken') ?? csrfFromBody

function normaliseErrors(raw: unknown): { errors: FieldErrors; general: string[] } {
  const errors: FieldErrors = {}
  const general: string[] = []
  if (!raw || typeof raw !== 'object') return { errors, general }
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    const messages = (Array.isArray(value) ? value : [value])
      .map((item) => typeof item === 'string' ? item : item && typeof item === 'object' && 'message' in item ? String((item as { message: unknown }).message) : null)
      .filter((item): item is string => Boolean(item))
    if (!messages.length) continue
    if (NON_FIELD_KEYS.includes(key)) general.push(...messages)
    else errors[key] = messages
  }
  return { errors, general }
}

export type ApiResponse<T> = { status: number; data: T }

type RequestOptions = { method?: string; body?: unknown; signal?: AbortSignal }

async function request<T>(path: string, { method = 'GET', body, signal }: RequestOptions, retried: boolean): Promise<ApiResponse<T>> {
  const upper = method.toUpperCase()
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (UNSAFE.has(upper)) {
    await ensureCsrf()
    const token = csrfToken()
    if (token) headers['X-CSRFToken'] = token
  }

  let response: Response
  try {
    response = await fetch(path, { method: upper, headers, credentials: 'same-origin', body: body === undefined ? undefined : JSON.stringify(body), signal })
  } catch (error) {
    if (isAbort(error)) throw error
    throw new ApiError(0)
  }

  const isJson = (response.headers.get('content-type') ?? '').includes('json')
  const data: unknown = response.status === 204 ? null : isJson ? await response.json().catch(() => null) : null

  if (!response.ok) {
    const record = data && typeof data === 'object' ? data as Record<string, unknown> : {}
    const detail = typeof record.detail === 'string' ? record.detail : null
    // Django's CSRF failure page is HTML (or a detail mentioning CSRF): refresh the token and retry once.
    if (response.status === 403 && UNSAFE.has(upper) && !retried && (!isJson || /csrf/i.test(detail ?? ''))) {
      await ensureCsrf(true)
      return request<T>(path, { method, body, signal }, true)
    }
    const { errors, general } = normaliseErrors(record.errors)
    throw new ApiError(response.status, detail, errors, general)
  }
  return { status: response.status, data: data as T }
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }, false),
  post: <T>(path: string, body?: unknown, signal?: AbortSignal) => request<T>(path, { method: 'POST', body: body ?? {}, signal }, false),
  patch: <T>(path: string, body: unknown, signal?: AbortSignal) => request<T>(path, { method: 'PATCH', body, signal }, false),
  delete: <T>(path: string, signal?: AbortSignal) => request<T>(path, { method: 'DELETE', signal }, false),
}
