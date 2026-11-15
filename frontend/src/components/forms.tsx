import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import type { SummaryItem } from './formState'

export type ControlProps = {
  id: string
  name: string
  'aria-invalid': true | undefined
  'aria-describedby': string | undefined
  required: boolean | undefined
}

type FieldProps = {
  id: string
  name: string
  label: string
  errors?: string[]
  hint?: ReactNode
  required?: boolean
  children: (control: ControlProps) => ReactNode
}

/** Label + control + hint + field error, wired with `aria-invalid` and `aria-describedby`. */
export function Field({ id, name, label, errors, hint, required, children }: FieldProps) {
  const invalid = Boolean(errors?.length)
  const describedBy = [hint ? `${id}-hint` : null, invalid ? `${id}-error` : null].filter(Boolean).join(' ') || undefined
  return (
    <div className={invalid ? 'field has-error' : 'field'}>
      <label htmlFor={id}>{label}{required ? <span className="field-flag"> (obligatorio)</span> : <span className="field-flag"> (opcional)</span>}</label>
      {hint && <p className="field-hint" id={`${id}-hint`}>{hint}</p>}
      {children({ id, name, 'aria-invalid': invalid || undefined, 'aria-describedby': describedBy, required: required || undefined })}
      {invalid && <p className="field-error" id={`${id}-error`}><span aria-hidden="true">⚠ </span>{errors!.join(' ')}</p>}
    </div>
  )
}

/**
 * Error summary shown above a form after a failed submit. Receives focus every time `attempt`
 * changes so screen-reader and keyboard users land on it; each item links to its field.
 */
export function ErrorSummary({ items, attempt, title = 'Revisa el formulario' }: { items: SummaryItem[]; attempt: number; title?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const hasItems = items.length > 0
  useEffect(() => {
    if (attempt > 0 && hasItems) ref.current?.focus()
  }, [attempt, hasItems])
  if (!hasItems) return null
  return (
    <div className="error-summary" role="alert" tabIndex={-1} ref={ref} aria-labelledby="error-summary-title">
      <h2 id="error-summary-title">{title}</h2>
      <ul>
        {items.map((item, index) => (
          <li key={`${item.id ?? 'general'}-${index}`}>
            {item.id
              // Links would change the hash route: focus the field without navigating.
              ? <a href={`#${item.id}`} onClick={(event) => { event.preventDefault(); document.getElementById(item.id!)?.focus() }}>{item.text}</a>
              : item.text}
          </li>
        ))}
      </ul>
    </div>
  )
}

/**
 * Submit button reflecting the pending state. It is not `disabled` (that would drop keyboard focus);
 * forms ignore submits while pending, and `aria-disabled` announces it.
 */
export function SubmitButton({ pending, children, pendingLabel }: { pending: boolean; children: ReactNode; pendingLabel: string }) {
  return (
    <button type="submit" className="button button-primary" aria-disabled={pending || undefined}>
      {pending ? <><span className="spinner" aria-hidden="true" /> {pendingLabel}</> : children}
    </button>
  )
}
