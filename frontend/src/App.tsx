import { useEffect, useRef } from 'react'
import './App.css'
import './pages/pages.css'
import AuthProvider from './auth/AuthProvider'
import { useAuth } from './auth/authContext'
import RequireAuth from './auth/RequireAuth'
import SiteHeader from './components/SiteHeader'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import ProfilePage from './pages/ProfilePage'
import RegisterPage from './pages/RegisterPage'
import SubmissionDetailPage from './pages/SubmissionDetailPage'
import SubmissionsPage from './pages/SubmissionsPage'
import SubmitPage from './pages/SubmitPage'
import { routeKey, STAFF_ROUTES, useRoute } from './router'
import type { Route } from './router'

function RouteView({ route }: { route: Route }) {
  switch (route.name) {
    case 'home': return <HomePage />
    case 'login': return <LoginPage next={route.next} />
    case 'register': return <RegisterPage next={route.next} />
    case 'notFound': return <NotFoundPage path={route.path} />
  }
  const page = (() => {
    switch (route.name) {
      case 'profile': return <ProfilePage />
      case 'submit': return <SubmitPage />
      case 'submissions': return <SubmissionsPage mode="own" />
      case 'submission': return <SubmissionDetailPage id={route.id} duplicate={route.duplicate} mode="own" />
      case 'review': return <SubmissionsPage mode="review" />
      case 'reviewItem': return <SubmissionDetailPage id={route.id} mode="review" />
    }
  })()
  return <RequireAuth staff={STAFF_ROUTES.has(route.name)}>{page}</RequireAuth>
}

/** Shell: header with account menu, hash routes and footer. The home view lives in pages/HomePage.tsx. */
function Shell() {
  const route = useRoute()
  const { me } = useAuth()
  const key = routeKey(route)
  const firstRender = useRef(true)

  // On navigation between views: scroll to top and move focus to the page heading (or <main>).
  useEffect(() => {
    if (firstRender.current) { firstRender.current = false; return }
    window.scrollTo(0, 0)
    const target = document.getElementById('page-title') ?? document.getElementById('inicio')
    target?.focus({ preventScroll: true })
  }, [key])

  // Private views are remounted when the account changes so no data from a previous session survives.
  const viewKey = route.name === 'home' ? 'home' : `${key}:${me?.id ?? 'anon'}`

  return (
    <div className="shell">
      <a className="skip-link" href="#inicio" onClick={(event) => { event.preventDefault(); document.getElementById('inicio')?.focus() }}>Saltar al contenido</a>
      <SiteHeader route={route} />
      <main id="inicio" tabIndex={-1}>
        <RouteView key={viewKey} route={route} />
      </main>
      <footer><span>GEO · OBSERVATORIO</span><span>HECHOS, FUENTES Y CONTEXTO.</span><span>UNA MIRADA AL MUNDO ↗</span></footer>
    </div>
  )
}

export default function App() {
  return <AuthProvider><Shell /></AuthProvider>
}
