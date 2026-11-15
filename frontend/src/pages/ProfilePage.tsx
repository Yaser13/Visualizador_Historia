import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { isAbort, toApiError } from '../api/client'
import type { ApiError } from '../api/client'
import { changePassword, fetchProfile, updateProfile } from '../api/endpoints'
import type { ProfileData } from '../api/endpoints'
import { useAuth, useSessionExpiry } from '../auth/authContext'
import { ErrorSummary, Field, SubmitButton } from '../components/forms'
import { COUNTRY, EMAIL, useFormFeedback } from '../components/formState'
import type { FieldDef } from '../components/formState'
import { ErrorState, LoadingState, PageFrame } from '../components/PageStates'

const PROFILE_FIELDS: FieldDef[] = [
  { name: 'display_name', label: 'Nombre visible' },
  { name: 'email', label: 'Correo electrónico' },
  { name: 'bio', label: 'Presentación' },
  { name: 'country', label: 'País' },
  { name: 'organization', label: 'Organización' },
  { name: 'language', label: 'Idioma' },
]
const PASSWORD_FIELDS: FieldDef[] = [
  { name: 'old_password', label: 'Contraseña actual' },
  { name: 'new_password', label: 'Nueva contraseña' },
  { name: 'new_password_confirm', label: 'Confirmar nueva contraseña' },
]

const REGION_NAMES = (() => { try { return new Intl.DisplayNames(['es'], { type: 'region' }) } catch { return null } })()
const countryName = (code: string) => {
  if (!COUNTRY.test(code)) return null
  try { const name = REGION_NAMES?.of(code); return name && name !== code ? name : null } catch { return null }
}

function validateProfile(values: ProfileData) {
  const errors: Record<string, string[]> = {}
  if (!values.display_name.trim()) errors.display_name = ['Escribe el nombre que verán los demás.']
  else if (values.display_name.trim().length > 80) errors.display_name = ['Usa como máximo 80 caracteres.']
  if (!values.email.trim()) errors.email = ['Escribe tu correo electrónico.']
  else if (!EMAIL.test(values.email.trim())) errors.email = ['Escribe un correo electrónico válido.']
  if (values.bio.length > 1000) errors.bio = ['Usa como máximo 1000 caracteres.']
  if (values.country && !COUNTRY.test(values.country)) errors.country = ['Usa el código ISO de 2 letras (por ejemplo, ES, MX, SD) o déjalo vacío.']
  if (values.organization.length > 120) errors.organization = ['Usa como máximo 120 caracteres.']
  return errors
}

function ProfileForm({ initial, onSaved, onError }: { initial: ProfileData; onSaved: (data: ProfileData) => void; onError: (error: ApiError) => void }) {
  const form = useFormFeedback('profile', PROFILE_FIELDS)
  const [values, setValues] = useState(initial)
  const [pending, setPending] = useState(false)
  const [saved, setSaved] = useState(false)
  const set = (name: keyof ProfileData) => (event: { target: { value: string } }) => {
    setSaved(false)
    setValues((previous) => ({ ...previous, [name]: name === 'country' ? event.target.value.toUpperCase().slice(0, 2) : event.target.value }))
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (pending) return
    const errors = validateProfile(values)
    if (Object.keys(errors).length) { form.fail(errors); return }
    setPending(true)
    setSaved(false)
    form.clear()
    try {
      const data = await updateProfile({ ...values, display_name: values.display_name.trim(), email: values.email.trim(), organization: values.organization.trim() })
      setValues(data)
      setSaved(true)
      onSaved(data)
    } catch (error) {
      const apiError = toApiError(error)
      onError(apiError)
      form.failWith(apiError)
    } finally {
      setPending(false)
    }
  }

  const country = countryName(values.country)
  return (
    <section className="form-section" aria-labelledby="profile-heading">
      <h2 id="profile-heading">Datos personales</h2>
      <ErrorSummary items={form.summary} attempt={form.attempt} title="No pudimos guardar el perfil" />
      <form className="form-card" noValidate onSubmit={submit} aria-busy={pending}>
        <Field id={form.fieldId('display_name')} name="display_name" label="Nombre visible" errors={form.errors.display_name} hint="Se muestra como autor de tus envíos publicados." required>
          {(control) => <input {...control} type="text" autoComplete="nickname" maxLength={80} value={values.display_name} onChange={set('display_name')} />}
        </Field>
        <Field id={form.fieldId('email')} name="email" label="Correo electrónico" errors={form.errors.email} hint="Privado: no se muestra públicamente." required>
          {(control) => <input {...control} type="email" autoComplete="email" inputMode="email" value={values.email} onChange={set('email')} />}
        </Field>
        <Field id={form.fieldId('bio')} name="bio" label="Presentación" errors={form.errors.bio} hint={`${values.bio.length} / 1000 caracteres.`}>
          {(control) => <textarea {...control} rows={4} maxLength={1000} value={values.bio} onChange={set('bio')} />}
        </Field>
        <div className="field-row">
          <Field id={form.fieldId('country')} name="country" label="País" errors={form.errors.country} hint={country ? `Código ISO de 2 letras · ${country}` : 'Código ISO de 2 letras, por ejemplo ES.'}>
            {(control) => <input {...control} type="text" autoComplete="country" autoCapitalize="characters" spellCheck={false} maxLength={2} className="input-short" value={values.country} onChange={set('country')} />}
          </Field>
          <Field id={form.fieldId('language')} name="language" label="Idioma" errors={form.errors.language}>
            {(control) => <select {...control} value={values.language} onChange={set('language')}><option value="es">Español</option><option value="en">English</option></select>}
          </Field>
        </div>
        <Field id={form.fieldId('organization')} name="organization" label="Organización" errors={form.errors.organization}>
          {(control) => <input {...control} type="text" autoComplete="organization" maxLength={120} value={values.organization} onChange={set('organization')} />}
        </Field>
        <div className="form-actions">
          <SubmitButton pending={pending} pendingLabel="Guardando…">Guardar perfil</SubmitButton>
          <p className="form-success" role="status">{saved ? 'Perfil guardado.' : ''}</p>
        </div>
      </form>
    </section>
  )
}

function PasswordForm({ onError }: { onError: (error: ApiError) => void }) {
  const form = useFormFeedback('password', PASSWORD_FIELDS)
  const [values, setValues] = useState({ old_password: '', new_password: '', new_password_confirm: '' })
  const [pending, setPending] = useState(false)
  const [saved, setSaved] = useState(false)
  const set = (name: keyof typeof values) => (event: { target: { value: string } }) => { setSaved(false); setValues((previous) => ({ ...previous, [name]: event.target.value })) }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (pending) return
    const errors: Record<string, string[]> = {}
    if (!values.old_password) errors.old_password = ['Escribe tu contraseña actual.']
    if (!values.new_password) errors.new_password = ['Escribe la nueva contraseña.']
    else if (values.new_password.length < 8) errors.new_password = ['Usa al menos 8 caracteres.']
    if (values.new_password && values.new_password_confirm !== values.new_password) errors.new_password_confirm = ['Las contraseñas no coinciden.']
    if (Object.keys(errors).length) { form.fail(errors); return }
    setPending(true)
    setSaved(false)
    form.clear()
    try {
      await changePassword(values.old_password, values.new_password)
      setValues({ old_password: '', new_password: '', new_password_confirm: '' })
      setSaved(true)
    } catch (error) {
      const apiError = toApiError(error)
      onError(apiError)
      form.failWith(apiError)
    } finally {
      setPending(false)
    }
  }

  return (
    <section className="form-section" aria-labelledby="password-heading">
      <h2 id="password-heading">Cambiar contraseña</h2>
      <ErrorSummary items={form.summary} attempt={form.attempt} title="No pudimos cambiar la contraseña" />
      <form className="form-card" noValidate onSubmit={submit} aria-busy={pending}>
        <Field id={form.fieldId('old_password')} name="old_password" label="Contraseña actual" errors={form.errors.old_password} required>
          {(control) => <input {...control} type="password" autoComplete="current-password" value={values.old_password} onChange={set('old_password')} />}
        </Field>
        <Field id={form.fieldId('new_password')} name="new_password" label="Nueva contraseña" errors={form.errors.new_password} hint="Al menos 8 caracteres. La sesión actual se mantiene abierta." required>
          {(control) => <input {...control} type="password" autoComplete="new-password" value={values.new_password} onChange={set('new_password')} />}
        </Field>
        <Field id={form.fieldId('new_password_confirm')} name="new_password_confirm" label="Confirmar nueva contraseña" errors={form.errors.new_password_confirm} required>
          {(control) => <input {...control} type="password" autoComplete="new-password" value={values.new_password_confirm} onChange={set('new_password_confirm')} />}
        </Field>
        <div className="form-actions">
          <SubmitButton pending={pending} pendingLabel="Actualizando…">Cambiar contraseña</SubmitButton>
          <p className="form-success" role="status">{saved ? 'Contraseña actualizada.' : ''}</p>
        </div>
      </form>
    </section>
  )
}

type LoadState = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'success'; data: ProfileData }

export default function ProfilePage() {
  const { me, updateMe } = useAuth()
  const onSessionError = useSessionExpiry()
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    fetchProfile(controller.signal)
      .then((data) => setState({ status: 'success', data }))
      .catch((error) => {
        if (isAbort(error)) return
        const apiError = toApiError(error)
        onSessionError(apiError)
        setState({ status: 'error', error: apiError })
      })
    return () => controller.abort()
  }, [attempt, onSessionError])

  const onSaved = (data: ProfileData) => {
    if (!me) return
    const { email, ...profile } = data
    updateMe({ ...me, email, profile })
  }

  return (
    <PageFrame eyebrow="CUENTA" title="Mi perfil" intro={me && <p>Usuario: <strong>{me.username}</strong>{me.is_staff && ' · equipo editorial'}. Tu nombre visible es el único dato que se muestra junto a tus envíos publicados.</p>}>
      {state.status === 'loading' && <LoadingState>Cargando tu perfil…</LoadingState>}
      {state.status === 'error' && <ErrorState message={state.error.userMessage} onRetry={() => { setState({ status: 'loading' }); setAttempt((value) => value + 1) }} />}
      {state.status === 'success' && <div className="profile-grid">
        <ProfileForm initial={state.data} onSaved={onSaved} onError={onSessionError} />
        <PasswordForm onError={onSessionError} />
      </div>}
    </PageFrame>
  )
}
