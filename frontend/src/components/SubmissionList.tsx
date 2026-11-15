import type { Submission } from '../api/types'
import { href } from '../router'
import { StatusBadge } from './Badges'
import { formatDateTime, hostOf } from './format'

/** List of submissions (own submissions or review queue) with status badge, dates and link to the detail. */
export default function SubmissionList({ items, basePath, showSubmitter = false }: { items: Submission[]; basePath: '/envios' | '/revision'; showSubmitter?: boolean }) {
  return (
    <ul className="submission-list">
      {items.map((item) => {
        const created = formatDateTime(item.created_at)
        const updated = formatDateTime(item.updated_at)
        return (
          <li key={item.id} className="submission-item">
            <div className="submission-main">
              <StatusBadge status={item.status} label={item.status_label} />
              <h2 className="submission-title"><a href={href(`${basePath}/${item.id}`)}>{item.event_title || `Envío n.º ${item.id} · ${hostOf(item.url)}`}</a></h2>
              <p className="submission-url">{item.url}</p>
              {item.step_detail && !['published', 'rejected'].includes(item.status) && <p className="submission-detail">{item.step_detail}</p>}
            </div>
            <dl className="submission-meta">
              {showSubmitter && <><dt>Enviado por</dt><dd>{item.submitted_by ?? 'No disponible'}</dd></>}
              <dt>Enviado</dt><dd>{created ? <time dateTime={item.created_at}>{created}</time> : 'Fecha no disponible'}</dd>
              <dt>Actualizado</dt><dd>{updated ? <time dateTime={item.updated_at}>{updated}</time> : 'Fecha no disponible'}</dd>
            </dl>
          </li>
        )
      })}
    </ul>
  )
}
