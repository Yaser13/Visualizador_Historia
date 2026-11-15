import { createContext, useCallback, useContext } from 'react'
import type { ApiError } from '../api/client'
import type { RegisterPayload } from '../api/endpoints'
import type { User } from '../api/types'

export type AuthStatus = 'loading' | 'anonymous' | 'authenticated' | 'error'

export type AuthContextValue = {
  status: AuthStatus
  /** Current user, or null when anonymous / unknown. */
  me: User | null
  /** Error of the last `GET /api/auth/me/` when status is `error` (server unreachable). */
  error: ApiError | null
  login: (username: string, password: string) => Promise<User>
  register: (payload: RegisterPayload) => Promise<User>
  logout: () => Promise<void>
  /** Re-reads `/api/auth/me/` (e.g. after a 401 from a private endpoint). */
  refresh: () => Promise<void>
  /** Replaces the cached user after a profile update. */
  updateMe: (user: User) => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}

/**
 * Returns a handler for errors of private endpoints: a 401 means the session expired, so the session
 * is re-read and the route guard sends the user to `#/entrar?next=…`.
 */
export function useSessionExpiry() {
  const { refresh } = useAuth()
  return useCallback((error: ApiError) => {
    if (error.status === 401) void refresh()
  }, [refresh])
}
