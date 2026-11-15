import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { toApiError } from '../api/client'
import { useAuth } from '../auth/authContext'
import { ErrorSummary, Field, SubmitButton } from '../components/forms'
import { EMAIL, USERNAME, useFormFeedback } from '../components/formState'
import type { FieldDef } from '../components/formState'
import { LoadingState, PageFrame } from '../components/PageStates'
import { href, navigate } from '../router'

const FIELDS: FieldDef[] = [
  { name: 'username', label: 'Usuario' },
  { name: 'email', label: 'Correo electrónico' },
  { name: 'display_name', label: 'Nombre visible' },
  { name: 'password', label: 'Contraseña' },
  { name: 'password_confirm', label: 'Confirmar contraseña' },
]
type Values = Record<'username' | 'email' | 'display_name' | 'password' | 'password_confirm', string>
const EMPTY: Values = { username: '', email: '', display_name: '', password: '', password_confirm: '' }

function validate(values: Values) {
  const errors: Record<string, string[]> = {}
  if (!values.username.trim()) errors.username = ['Elige un nombre de usuario.']
  else if (!USERNAME.test(values.username.trim())) errors.username = ['Usa hasta 150 letras, números o los signos @ . + - _ (sin espacios).']
  if (!values.email.trim()) errors.email = ['Escribe tu correo electrónico.']
  else if (!EMAIL.test(values.email.trim())) errors.email = ['Escribe un correo electrónico válido, por ejemplo nombre@dominio.org.']
  if (!values.display_name.trim()) errors.display_name = ['Escribe el nombre que verán los demás.']
  else if (values.display_name.trim().length > 80) errors.display_name = ['Usa como máximo 80 caracteres.']
  if (!values.password) errors.password = ['Elige una contraseña.']
  else if (values.password.length < 8) errors.password = ['Usa al menos 8 caracteres.']
  if (values.password && values.password_confirm !== values.password) errors.password_confirm = ['Las contraseñas no coinciden.']
  return errors
}

export default function RegisterPage({ next }: { next: string | null }) {
  const { status, register } = useAuth()
  const form = useFormFeedback('register', FIELDS)
  const [values, setValues] = useState<Values>(EMPTY)
  const [pending, setPending] = useState(false)

  useEffect(() => { if (status === 'authenticated') navigate(next ?? '/perfil', { replace: true }) }, [status, next])

  const set = (name: keyof Values) => (event: { target: { value: string } }) => setValues((previous) => ({ ...previous, [name]: event.target.value }))

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (pending) return
    const errors = validate(values)
    if (Object.keys(errors).length) { form.fail(errors); return }
    setPending(true)
    form.clear()
    try {
      await register({ username: values.username.trim(), email: values.email.trim(), display_name: values.display_name.trim(), password: values.password })
    } catch (error) {
      setValues((previous) => ({ ...previous, password: '', password_confirm: '' }))
      form.failWith(toApiError(error))
    } finally {
      setPending(false)
    }
  }

  if (status === 'authenticated') return <LoadingState>Cuenta lista. Redirigiendo…</LoadingState>

  return (
    <PageFrame eyebrow="CUENTA" title="Crear cuenta" intro={<p>Con una cuenta puedes enviar enlaces de noticias para que se analicen con fuentes verificables y seguir su estado.</p>}>
      <ErrorSummary items={form.summary} attempt={form.attempt} title="No pudimos crear la cuenta" />
      <form className="form-card" noValidate onSubmit={submit} aria-busy={pending}>
        <Field id={form.fieldId('username')} name="username" label="Usuario" errors={form.errors.username} hint="Para iniciar sesión. No se muestra públicamente." required>
          {(control) => <input {...control} type="text" autoComplete="username" autoCapitalize="none" spellCheck={false} maxLength={150} value={values.username} onChange={set('username')} />}
        </Field>
        <Field id={form.fieldId('email')} name="email" label="Correo electrónico" errors={form.errors.email} hint="No se muestra públicamente." required>
          {(control) => <input {...control} type="email" autoComplete="email" inputMode="email" value={values.email} onChange={set('email')} />}
        </Field>
        <Field id={form.fieldId('display_name')} name="display_name" label="Nombre visible" errors={form.errors.display_name} hint="Aparece como autor de tus envíos publicados." required>
          {(control) => <input {...control} type="text" autoComplete="nickname" maxLength={80} value={values.display_name} onChange={set('display_name')} />}
        </Field>
        <Field id={form.fieldId('password')} name="password" label="Contraseña" errors={form.errors.password} hint="Al menos 8 caracteres. El servidor aplica además sus reglas de seguridad (no demasiado común ni parecida a tus datos)." required>
          {(control) => <input {...control} type="password" autoComplete="new-password" value={values.password} onChange={set('password')} />}
        </Field>
        <Field id={form.fieldId('password_confirm')} name="password_confirm" label="Confirmar contraseña" errors={form.errors.password_confirm} required>
          {(control) => <input {...control} type="password" autoComplete="new-password" value={values.password_confirm} onChange={set('password_confirm')} />}
        </Field>
        <div className="form-actions">
          <SubmitButton pending={pending} pendingLabel="Creando cuenta…">Crear cuenta</SubmitButton>
        </div>
        <p className="form-alt">¿Ya tienes cuenta? <a href={href(next ? `/entrar?next=${encodeURIComponent(next)}` : '/entrar')}>Entrar</a>.</p>
      </form>
    </PageFrame>
  )
}
