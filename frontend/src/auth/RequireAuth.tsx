import { useEffect } from 'react'
import type { ReactNode } from 'react'
import { ErrorState, LoadingState, PageFrame } from '../components/PageStates'
import { currentPath, href, loginPath, navigate, parseHash, PRIVATE_ROUTES } from '../router'
import { useAuth } from './authContext'

/**
 * Route guard for private views. It only improves the experience: every endpoint is protected by
 * Django (401/403), which remains the authority.
 */
export default function RequireAuth({ staff = false, children }: { staff?: boolean; children: ReactNode }) {
  const { status, me, error, refresh } = useAuth()

  useEffect(() => {
    if (status !== 'anonymous') return
    // After a logout the hash may already point to a public page: do not send the user to the login form.
    if (!PRIVATE_ROUTES.has(parseHash(window.location.hash).name)) return
    navigate(loginPath(currentPath()), { replace: true })
  }, [status])

  if (status === 'loading') return <LoadingState>Comprobando la sesión…</LoadingState>
  if (status === 'error' && !me) {
    return (
      <PageFrame eyebrow="CUENTA" title="No pudimos comprobar tu sesión">
        <ErrorState title="El servidor no respondió." message={error?.userMessage ?? 'Inténtalo de nuevo en unos momentos.'} onRetry={() => { void refresh() }} />
      </PageFrame>
    )
  }
  if (!me) return <LoadingState>Redirigiendo a la página de acceso…</LoadingState>
  if (staff && !me.is_staff) {
    return (
      <PageFrame eyebrow="EQUIPO EDITORIAL" title="Acceso restringido" intro={<p>Esta sección es solo para el equipo editorial.</p>}>
        <p className="back-link"><a href={href('/')}>Volver al inicio</a></p>
      </PageFrame>
    )
  }
  return children
}
