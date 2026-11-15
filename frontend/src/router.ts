// Hash router without dependencies. Only hashes starting with `#/` are routes; every other hash
// (`#noticia=<slug>`, `#claim-…`, `#inicio`, empty) belongs to the home page, which keeps handling it.
import { useMemo, useSyncExternalStore } from 'react'

export type Route =
  | { name: 'home' }
  | { name: 'login'; next: string | null }
  | { name: 'register'; next: string | null }
  | { name: 'profile' }
  | { name: 'submit' }
  | { name: 'submissions' }
  | { name: 'submission'; id: number; duplicate: boolean }
  | { name: 'review' }
  | { name: 'reviewItem'; id: number }
  | { name: 'notFound'; path: string }

/** Routes that need a session; the shell redirects to `#/entrar?next=…` when there is none. */
export const PRIVATE_ROUTES: ReadonlySet<Route['name']> = new Set(['profile', 'submit', 'submissions', 'submission', 'review', 'reviewItem'])
export const STAFF_ROUTES: ReadonlySet<Route['name']> = new Set(['review', 'reviewItem'])

const ID = /^[1-9]\d{0,9}$/
/** Internal paths accepted as `next` (prevents redirects to arbitrary or malformed values). */
const SAFE_PATH = /^\/(?:[a-z]+(?:\/[1-9]\d{0,9})?)?(?:\?[\w=&%-]*)?$/

export const safeNext = (value: string | null) => value && SAFE_PATH.test(value) && !value.startsWith('/entrar') && !value.startsWith('/registro') ? value : null

export function parseHash(hash: string): Route {
  if (!hash.startsWith('#/')) return { name: 'home' }
  const [rawPath, rawQuery = ''] = hash.slice(1).split('?', 2)
  const path = rawPath.replace(/\/+$/, '') || '/'
  const query = new URLSearchParams(rawQuery)
  const parts = path.split('/').filter(Boolean)
  const id = parts[1] && ID.test(parts[1]) ? Number(parts[1]) : null
  switch (parts[0]) {
    case undefined: return { name: 'home' }
    case 'entrar': if (parts.length === 1) return { name: 'login', next: safeNext(query.get('next')) }; break
    case 'registro': if (parts.length === 1) return { name: 'register', next: safeNext(query.get('next')) }; break
    case 'perfil': if (parts.length === 1) return { name: 'profile' }; break
    case 'enviar': if (parts.length === 1) return { name: 'submit' }; break
    case 'envios':
      if (parts.length === 1) return { name: 'submissions' }
      if (parts.length === 2 && id !== null) return { name: 'submission', id, duplicate: query.get('existente') === '1' }
      break
    case 'revision':
      if (parts.length === 1) return { name: 'review' }
      if (parts.length === 2 && id !== null) return { name: 'reviewItem', id }
      break
  }
  return { name: 'notFound', path }
}

/** Current path of a route hash (`/envios/3`), used as `next` after login. */
export const currentPath = () => {
  const hash = window.location.hash
  return hash.startsWith('#/') ? hash.slice(1) : '/'
}

export const href = (path: string) => `#${path}`

/** Navigates to an internal path (`/perfil`). `replace` avoids adding a history entry (redirects). */
export function navigate(path: string, { replace = false } = {}) {
  const target = href(path)
  if (window.location.hash === target) return
  if (replace) window.location.replace(target)
  else window.location.hash = target
}

export const loginPath = (next: string) => `/entrar?next=${encodeURIComponent(next)}`

const subscribe = (onChange: () => void) => {
  window.addEventListener('hashchange', onChange)
  return () => window.removeEventListener('hashchange', onChange)
}
const getHash = () => window.location.hash

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, getHash, () => '')
  return useMemo(() => parseHash(hash), [hash])
}

/** Stable key used to remount pages and move focus on navigation (ignores home-internal hashes). */
export const routeKey = (route: Route) => 'id' in route ? `${route.name}:${route.id}` : route.name
