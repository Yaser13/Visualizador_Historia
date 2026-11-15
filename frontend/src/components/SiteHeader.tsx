import { useEffect, useId, useRef, useState } from 'react'
import type { FocusEvent, KeyboardEvent } from 'react'
import { toApiError } from '../api/client'
import { displayName } from '../api/endpoints'
import { useAuth } from '../auth/authContext'
import { href, navigate, routeKey } from '../router'
import type { Route } from '../router'

type MenuLink = { path: string; label: string; current: boolean }

/** Disclosure menu of the signed-in user (button + list of links), operable with the keyboard. */
function UserMenu({ route }: { route: Route }) {
  const { me, logout } = useAuth()
  // The menu belongs to the route where it was opened: navigating closes it without an effect.
  const [openAt, setOpenAt] = useState<string | null>(null)
  const key = routeKey(route)
  const open = openAt === key
  const setOpen = (value: boolean) => setOpenAt(value ? key : null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const container = useRef<HTMLDivElement>(null)
  const button = useRef<HTMLButtonElement>(null)
  const menuId = useId()

  // Close on clicks outside.
  useEffect(() => {
    if (!open) return
    const onPointer = (event: PointerEvent) => { if (!container.current?.contains(event.target as Node)) setOpenAt(null) }
    document.addEventListener('pointerdown', onPointer)
    return () => document.removeEventListener('pointerdown', onPointer)
  }, [open])

  if (!me) return null
  const links: MenuLink[] = [
    { path: '/perfil', label: 'Mi perfil', current: route.name === 'profile' },
    { path: '/enviar', label: 'Enviar noticia', current: route.name === 'submit' },
    { path: '/envios', label: 'Mis envíos', current: route.name === 'submissions' || route.name === 'submission' },
    ...(me.is_staff ? [{ path: '/revision', label: 'Revisión', current: route.name === 'review' || route.name === 'reviewItem' }] : []),
  ]

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && open) { event.preventDefault(); setOpen(false); button.current?.focus() }
  }
  const onBlur = (event: FocusEvent) => {
    if (open && event.relatedTarget && !container.current?.contains(event.relatedTarget as Node)) setOpen(false)
  }
  const signOut = async () => {
    if (pending) return
    setPending(true)
    setError(null)
    try {
      await logout()
      setOpen(false)
      navigate('/')
    } catch (failure) {
      setError(toApiError(failure).userMessage)
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="user-menu" ref={container} onKeyDown={onKeyDown} onBlur={onBlur}>
      <button type="button" ref={button} className="user-menu-button" aria-expanded={open} aria-controls={menuId} onClick={() => setOpen(!open)}>
        <span className="user-avatar" aria-hidden="true">{displayName(me).slice(0, 1).toUpperCase()}</span>
        <span className="user-name"><span className="sr-only">Menú de </span>{displayName(me)}</span>
        <span className="user-caret" aria-hidden="true">▾</span>
      </button>
      <div className="user-menu-panel" id={menuId} hidden={!open}>
        <p className="user-menu-who">Sesión iniciada como <strong>{me.username}</strong>{me.is_staff && <> · equipo editorial</>}</p>
        <ul>
          {links.map((link) => <li key={link.path}><a href={href(link.path)} aria-current={link.current ? 'page' : undefined}>{link.label}</a></li>)}
          <li><button type="button" onClick={signOut} aria-disabled={pending || undefined}>{pending ? 'Cerrando sesión…' : 'Salir'}</button></li>
        </ul>
        {error && <p className="user-menu-error" role="alert">{error}</p>}
      </div>
    </div>
  )
}

export default function SiteHeader({ route }: { route: Route }) {
  const { status } = useAuth()
  return (
    <header className="topbar">
      <a href="#inicio" className="brand"><span className="brand-icon" aria-hidden="true">✳</span> GEO · OBSERVATORIO</a>
      <span className="topbar-context">CONTEXTO PARA ENTENDER EL MUNDO</span>
      <span className="topbar-series">INFORMACIÓN <span>/ GEOPOLÍTICA</span></span>
      <nav className="account-nav" aria-label="Cuenta">
        {status === 'loading' && <span className="account-pending" role="status"><span className="spinner" aria-hidden="true" /><span className="sr-only">Comprobando la sesión…</span></span>}
        {(status === 'anonymous' || status === 'error') && <>
          <a className="account-link" href={href('/entrar')} aria-current={route.name === 'login' ? 'page' : undefined}>Entrar</a>
          <a className="account-link account-primary" href={href('/registro')} aria-current={route.name === 'register' ? 'page' : undefined}>Crear cuenta</a>
        </>}
        {status === 'authenticated' && <UserMenu route={route} />}
      </nav>
    </header>
  )
}
