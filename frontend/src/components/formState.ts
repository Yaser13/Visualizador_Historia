// Form feedback state shared by the account and submission forms: field errors, general errors and a
// counter that changes on every failed submit (the error summary receives focus when it changes).
import { useCallback, useState } from 'react'
import type { ApiError, FieldErrors } from '../api/client'

export type FieldDef = { name: string; label: string }
export type SummaryItem = { id?: string; text: string }

type Feedback = { errors: FieldErrors; general: string[]; attempt: number }

export function useFormFeedback(formId: string, fields: FieldDef[]) {
  const [feedback, setFeedback] = useState<Feedback>({ errors: {}, general: [], attempt: 0 })

  const fail = useCallback((errors: FieldErrors, general: string[] = []) => {
    setFeedback((previous) => ({ errors, general, attempt: previous.attempt + 1 }))
  }, [])

  /** Maps an API error: known fields stay attached to their input, the rest goes to the summary. */
  const failWith = useCallback((error: ApiError) => {
    const known = new Set(fields.map((field) => field.name))
    const errors: FieldErrors = {}
    const general = [...(error.detail ? [error.detail] : []), ...error.general]
    for (const [name, messages] of Object.entries(error.errors)) {
      if (known.has(name)) errors[name] = messages
      else general.push(...messages)
    }
    if (!general.length && !Object.keys(errors).length) general.push(error.userMessage)
    fail(errors, general)
  }, [fields, fail])

  const clear = useCallback(() => setFeedback((previous) => ({ errors: {}, general: [], attempt: previous.attempt })), [])

  const fieldId = (name: string) => `${formId}-${name}`
  const summary: SummaryItem[] = [
    ...fields.flatMap((field) => (feedback.errors[field.name] ?? []).map((text) => ({ id: fieldId(field.name), text: `${field.label}: ${text}` }))),
    ...feedback.general.map((text) => ({ text })),
  ]

  return { errors: feedback.errors, attempt: feedback.attempt, summary, fail, failWith, clear, fieldId }
}

/** Client-side checks shared by several forms (the server validates again). */
export const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
export const USERNAME = /^[\w.@+-]{1,150}$/
export const COUNTRY = /^[A-Z]{2}$/

export function isHttpUrl(value: string) {
  try {
    const url = new URL(value)
    return (url.protocol === 'http:' || url.protocol === 'https:') && Boolean(url.hostname)
  } catch { return false }
}
