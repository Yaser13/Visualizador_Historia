import type { ReactNode } from 'react'

export function LoadingState({ children = 'Cargando…' }: { children?: ReactNode }) {
  return <p className="page-state" role="status"><span className="spinner" aria-hidden="true" /> {children}</p>
}

export function ErrorState({ title = 'No pudimos cargar esta información.', message, onRetry, children }: { title?: string; message: string; onRetry?: () => void; children?: ReactNode }) {
  return (
    <div className="page-state page-error" role="alert">
      <p className="page-state-title">{title}</p>
      <p>{message}</p>
      {children}
      {onRetry && <button type="button" className="button" onClick={onRetry}>Intentar de nuevo</button>}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="page-state page-empty">
      <p className="page-state-title">{title}</p>
      {children}
    </div>
  )
}

/** Page wrapper: eyebrow, focusable h1 (receives focus on navigation) and optional intro. */
export function PageFrame({ eyebrow, title, intro, children, wide = false }: { eyebrow: string; title: string; intro?: ReactNode; children: ReactNode; wide?: boolean }) {
  return (
    <div className={wide ? 'page page-wide' : 'page'}>
      <p className="eyebrow">{eyebrow}</p>
      <h1 id="page-title" tabIndex={-1}>{title}</h1>
      {intro && <div className="page-intro">{intro}</div>}
      {children}
    </div>
  )
}
