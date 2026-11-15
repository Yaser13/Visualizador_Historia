import { useCallback, useEffect, useRef, useState } from 'react'
import { isAbort, toApiError } from '../api/client'
import type { ApiError } from '../api/client'
import { fetchSubmission } from '../api/endpoints'
import { TERMINAL_STATUSES } from '../api/types'
import type { SubmissionDetail } from '../api/types'

export const POLL_MS = 4000

export type PolledState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'success'; data: SubmissionDetail; pollError: ApiError | null; polling: boolean }

/** Transient errors keep polling (the last good data stays on screen); 401/403/404 stop it. */
const isTransient = (error: ApiError) => error.isNetwork || error.status === 429 || error.status >= 500

/**
 * Loads `GET /api/submissions/<id>/` and polls every 4 s while the status is not terminal. Polling
 * waits for each response (no overlapping requests), pauses while the tab is hidden (resuming with
 * an immediate request when it becomes visible again) and stops on unmount.
 */
export function useSubmissionPolling(id: number, onError?: (error: ApiError) => void) {
  const [state, setState] = useState<PolledState>({ status: 'loading' })
  const [generation, setGeneration] = useState(0)
  const hasData = useRef(false)
  const onErrorRef = useRef(onError)
  useEffect(() => { onErrorRef.current = onError }, [onError])

  useEffect(() => {
    let disposed = false
    let timer: number | undefined
    let controller: AbortController | null = null
    let wantsPoll = false

    const clearTimer = () => { if (timer !== undefined) { window.clearTimeout(timer); timer = undefined } }
    const schedule = () => {
      clearTimer()
      wantsPoll = true
      if (document.visibilityState !== 'hidden') timer = window.setTimeout(load, POLL_MS)
    }
    async function load() {
      timer = undefined
      wantsPoll = false
      controller?.abort()
      controller = new AbortController()
      try {
        const data = await fetchSubmission(id, controller.signal)
        if (disposed) return
        hasData.current = true
        const polling = !TERMINAL_STATUSES.has(data.status)
        setState({ status: 'success', data, pollError: null, polling })
        if (polling) schedule()
      } catch (error) {
        if (disposed || isAbort(error)) return
        const apiError = toApiError(error)
        onErrorRef.current?.(apiError)
        if (hasData.current) {
          const keep = isTransient(apiError)
          setState((previous) => previous.status === 'success' ? { ...previous, pollError: apiError, polling: keep } : { status: 'error', error: apiError })
          if (keep) schedule()
        } else {
          setState({ status: 'error', error: apiError })
        }
      }
    }
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') {
        if (timer !== undefined) { clearTimer(); wantsPoll = true }
      } else if (wantsPoll && timer === undefined) {
        void load()
      }
    }

    void load()
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      disposed = true
      clearTimer()
      controller?.abort()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [id, generation])

  /** Reloads now (e.g. after retry / publish / reject) and resumes polling if needed. */
  const reload = useCallback(() => {
    setState((previous) => previous.status === 'error' ? { status: 'loading' } : previous)
    setGeneration((value) => value + 1)
  }, [])

  return { state, reload }
}
