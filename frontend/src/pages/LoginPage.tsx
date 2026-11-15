import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { toApiError } from '../api/client'
import { useAuth } from '../auth/authContext'
import { ErrorSummary, Field, SubmitButton } from '../components/forms'
import { useFormFeedback } from '../components/formState'
import type { FieldDef } from '../components/formState'
import { LoadingState, PageFrame } from '../components/PageStates'
import { href, navigate } from '../router'

const FIELDS: FieldDef[] = [{ name: 'username', label: 'Usuario' }, { name: 'password', label: 'Contraseña' }]

export default function LoginPage({ next }: { next: string | null }) {
  const { status, login } = useAuth()
  const form = useFormFeedback('login', FIELDS)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)

  // Signed in (now or already): go back to where the user was.
  useEffect(() => { if (status === 'authenticated') navigate(next ?? '/', { replace: true }) }, [status, next])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (pending) return
    const errors: Record<string, string[]> = {}
    if (!username.trim()) errors.username = ['Escribe tu nombre de usuario.']
    if (!password) errors.password = ['Escribe tu contraseña.']
    if (Object.keys(errors).length) { form.fail(errors); return }
    setPending(true)
    form.clear()
    try {
      await login(username.trim(), password)
    } catch (error) {
      setPassword('')
      form.failWith(toApiError(error))
    } finally {
      setPending(false)
    }
  }

  if (status === 'authenticated') return <LoadingState>Sesión iniciada. Redirigiendo…</LoadingState>

  return (
    <PageFrame eyebrow="CUENTA" title="Entrar" intro={<p>Accede para enviar noticias, seguir su análisis y gestionar tu perfil.</p>}>
      {next && <p className="notice" role="status">Inicia sesión para continuar; volverás a la página que intentabas abrir.</p>}
      {status === 'error' && <p className="notice notice-warning">No pudimos comprobar la sesión con el servidor. Puedes intentar entrar de todos modos.</p>}
      <ErrorSummary items={form.summary} attempt={form.attempt} title="No pudimos iniciar sesión" />
      <form className="form-card" noValidate onSubmit={submit} aria-busy={pending}>
        <Field id={form.fieldId('username')} name="username" label="Usuario" errors={form.errors.username} required>
          {(control) => <input {...control} type="text" autoComplete="username" autoCapitalize="none" spellCheck={false} value={username} onChange={(event) => setUsername(event.target.value)} />}
        </Field>
        <Field id={form.fieldId('password')} name="password" label="Contraseña" errors={form.errors.password} required>
          {(control) => <input {...control} type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} />}
        </Field>
        <div className="form-actions">
          <SubmitButton pending={pending} pendingLabel="Entrando…">Entrar</SubmitButton>
        </div>
        <p className="form-alt">¿No tienes cuenta? <a href={href(next ? `/registro?next=${encodeURIComponent(next)}` : '/registro')}>Crea una cuenta</a>.</p>
      </form>
    </PageFrame>
  )
}
