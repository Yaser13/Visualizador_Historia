import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { ensureCsrf, isAbort, toApiError } from '../api/client'
import type { ApiError } from '../api/client'
import * as endpoints from '../api/endpoints'
import type { RegisterPayload } from '../api/endpoints'
import type { User } from '../api/types'
import { AuthContext } from './authContext'
import type { AuthContextValue, AuthStatus } from './authContext'

type State = { status: AuthStatus; me: User | null; error: ApiError | null }

/**
 * Session state backed by Django's session cookie. Nothing is persisted in the browser: the user is
 * read from `GET /api/auth/me/` at start-up (after obtaining the CSRF cookie) and kept in memory.
 */
export default function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ status: 'loading', me: null, error: null })

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      await ensureCsrf()
      const me = await endpoints.fetchMe(signal)
      if (signal?.aborted) return
      setState({ status: me ? 'authenticated' : 'anonymous', me, error: null })
    } catch (error) {
      if (isAbort(error) || signal?.aborted) return
      setState((previous) => ({ status: 'error', me: previous.me, error: toApiError(error) }))
    }
  }, [])

  // Start-up: CSRF cookie first, then the current session.
  useEffect(() => {
    const controller = new AbortController()
    ensureCsrf()
      .then(() => endpoints.fetchMe(controller.signal))
      .then((me) => setState({ status: me ? 'authenticated' : 'anonymous', me, error: null }))
      .catch((error) => { if (!isAbort(error) && !controller.signal.aborted) setState({ status: 'error', me: null, error: toApiError(error) }) })
    return () => controller.abort()
  }, [])

  const signedIn = useCallback((me: User) => {
    setState({ status: 'authenticated', me, error: null })
    // Django rotates the CSRF token on login; refresh the fallback copy in case the cookie is unreadable.
    void ensureCsrf(true)
    return me
  }, [])

  const value = useMemo<AuthContextValue>(() => ({
    ...state,
    login: async (username, password) => signedIn(await endpoints.login(username, password)),
    register: async (payload: RegisterPayload) => signedIn(await endpoints.register(payload)),
    logout: async () => {
      try {
        await endpoints.logout()
      } catch (error) {
        // 401/403 mean there is no valid session any more: treat as signed out.
        const apiError = toApiError(error)
        if (apiError.status !== 401 && apiError.status !== 403) throw apiError
      }
      setState({ status: 'anonymous', me: null, error: null })
      void ensureCsrf(true)
    },
    refresh: async () => {
      setState((previous) => previous.status === 'error' ? { ...previous, status: 'loading' } : previous)
      await load()
    },
    updateMe: (me: User) => setState({ status: 'authenticated', me, error: null }),
  }), [state, load, signedIn])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
