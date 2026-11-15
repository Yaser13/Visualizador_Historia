import { PageFrame } from '../components/PageStates'
import { href } from '../router'

export default function NotFoundPage({ path }: { path: string }) {
  return (
    <PageFrame eyebrow="ERROR 404" title="Página no encontrada" intro={<p>La dirección <code>#{path}</code> no corresponde a ninguna sección del observatorio.</p>}>
      <p className="back-link"><a href={href('/')}>Volver al inicio</a></p>
    </PageFrame>
  )
}
