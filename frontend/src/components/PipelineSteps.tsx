import type { AgentRun } from '../api/types'

const STEPS = [
  { key: 'fetching', label: 'Descarga' },
  { key: 'researching', label: 'Cobertura relacionada' },
  { key: 'extracting', label: 'Extracción' },
  { key: 'verifying', label: 'Verificación de citas' },
  { key: 'geolocating', label: 'Ubicación' },
  { key: 'analyzing', label: 'Análisis' },
  { key: 'review', label: 'Revisión editorial' },
] as const

/** Step reached by each agent (used to locate where a failed submission stopped). */
const AGENT_STEP: Record<string, number> = { researcher: 1, extractor: 2, verifier: 3, geolocator: 4, analyst: 5 }

type StepState = 'done' | 'current' | 'pending' | 'error'
const STATE_TEXT: Record<StepState, string> = { done: 'completado', current: 'en curso', pending: 'pendiente', error: 'interrumpido' }

/** Index of the step where a failed submission stopped: the last agent with an error, else after the last agent that ran. */
function failedStep(runs: AgentRun[]) {
  const errored = [...runs].reverse().find((run) => run.status === 'error' && run.agent in AGENT_STEP)
  if (errored) return AGENT_STEP[errored.agent]
  const indexes = runs.map((run) => AGENT_STEP[run.agent]).filter((value): value is number => value !== undefined)
  return indexes.length ? Math.min(Math.max(...indexes) + 1, STEPS.length - 1) : 0
}

/**
 * Progress of the pipeline: fetching → … → review → published / rejected / failed.
 * Each step has a visible text state (not only colour); the current one has `aria-current="step"`.
 */
export default function PipelineSteps({ status, runs }: { status: string; runs: AgentRun[] }) {
  const index = STEPS.findIndex((step) => step.key === status)
  const failedAt = status === 'failed' ? failedStep(runs) : -1
  const finalLabel = status === 'published' ? 'Publicada' : status === 'rejected' ? 'Rechazada' : 'Publicación'

  const stateOf = (position: number): StepState => {
    if (status === 'published' || status === 'rejected') return 'done'
    if (status === 'failed') return position < failedAt ? 'done' : position === failedAt ? 'error' : 'pending'
    if (status === 'queued' || index < 0) return 'pending'
    return position < index ? 'done' : position === index ? 'current' : 'pending'
  }
  const finalState: StepState = status === 'published' ? 'done' : status === 'rejected' ? 'error' : 'pending'
  const items = [
    ...STEPS.map((step, position) => ({ key: step.key, label: step.label, state: stateOf(position) })),
    { key: 'final', label: finalLabel, state: finalState },
  ]

  return (
    <ol className="pipeline" aria-label="Progreso del análisis">
      {items.map((item, position) => (
        <li key={item.key} className={`pipeline-step is-${item.state}`} aria-current={item.state === 'current' ? 'step' : undefined}>
          <span className="pipeline-marker" aria-hidden="true">{item.state === 'done' ? '✓' : item.state === 'error' ? '!' : position + 1}</span>
          <span className="pipeline-label">{item.label}</span>
          <span className="pipeline-state">{item.key === 'final' && status === 'rejected' ? 'no publicada' : STATE_TEXT[item.state]}</span>
        </li>
      ))}
    </ol>
  )
}
