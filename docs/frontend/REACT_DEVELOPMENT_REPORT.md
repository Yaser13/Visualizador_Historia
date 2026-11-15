# Reporte de implementación React — diseño centrado en el globo

Fecha: 2026-11-15. Estado: IMPLEMENTED, pendiente de revisión visual y accesibilidad. Base: 2c7534a con cambios locales compartidos.

## Resumen y archivos

`frontend/src/App.tsx` presenta el globo como área principal, una tarjeta breve con fuentes y navegación anterior/siguiente, cronología seleccionable y aviso de revisión. `App.css` e `index.css` adaptan el diseño a escritorio y móvil. Se conserva la interfaz de `Globe` y el endpoint Django; no se cambiaron contratos ni se inventaron iconos militares.

## Interfaz e integración

Persisten carga, error con reintento, lista vacía, fallback del globo, selección mediante botones con `aria-pressed`, enlaces de fuente histórica y geográfica y foco visible. En móvil se apilan el globo, controles y tarjeta. El flujo consume GET /api/stories/expansion-de-roma/ mediante proxy de desarrollo, sin autenticación. No existe OpenAPI formal.

## Validación y límites

`npm run build`: correcto (TypeScript y Vite), con aviso por módulo diferido de globo mayor a 500 kB. `npm run lint`: sin errores, una advertencia previa react/set-state-in-effect en Globe.tsx. No se han ejecutado pruebas visuales en navegador, pruebas de lector de pantalla ni verificaciones responsivas manuales. No hay pruebas de componentes configuradas. Pendiente revisión por arquitectura y QA, incluidos fuentes expandidas, teclado y fallo WebGL.

## Actualización: atlas visual de referencia — 2026-11-15

Estado IMPLEMENTED, pendiente de validación integrada. Los estilos de `App.css` e `index.css` sitúan el mapa en primer plano y adaptan panel, controles y cronología a un atlas oscuro. Se conservan los estados de carga/error, el contrato `Globe` y los enlaces existentes; no se incorporaron datos históricos nuevos. `npm run build` pasó con aviso de tamaño del módulo 3D; `npm run lint` pasó con una advertencia existente en `Globe.tsx`. No se afirma aún validación visual, táctil o con lector de pantalla.

## 2026-11-15 — Interfaz del observatorio geopolítico

Implementación para la ruta `GET /api/stories/geopolitica/` acordada con backend: noticia y coordenada seleccionada, icono por categoría, secciones de hechos y análisis diferenciadas, fechas y fuentes, aviso de instantánea sin actualización automática, y alternativas de carga/error. Archivos: `frontend/src/App.tsx`, `Globe.tsx`, `App.css`, `index.html`. Validación: `npm run build` y `npm run lint` sin errores; persisten advertencias del tamaño del módulo 3D y `react/set-state-in-effect`. Pendiente comprobación visual y funcional de la integración real, accesibilidad con lector de pantalla y dispositivos táctiles. No se modificó la API desde React.

## 2026-11-15 — Evidencia, actores y efectos

App.tsx presenta afirmaciones y fuentes por afirmación, roles de actores en español y efectos con perspectiva o ausencia de evidencia; las declaraciones se diferencian de los análisis y se enlazan las afirmaciones de respaldo. App.css añade formato para el detalle. Validación: build y lint sin errores, con avisos previos del globo; pendiente revisión visual integrada y accesibilidad con lector de pantalla.

## Iteración: selector y línea de tiempo de conflicto — 2026-11-15

Estado: IMPLEMENTED; pendiente integración real y QA de accesibilidad. Archivos: `frontend/src/App.tsx`, `frontend/src/App.css`. Se mantienen las noticias existentes y se agrega selección de conflicto/COP31, con solicitud cancelable, carga, error y reintento. La línea de tiempo permite elegir hitos y sincronizar lugar y símbolo con el globo. La leyenda evita interpretar iconos como posiciones o movimientos militares; se conserva información y fuentes por hito. La API prevista para conflicto es `/api/stories/conflicto-armado/` con shape y categorías coordinados con backend; no se ha verificado aún el endpoint integrado.

Validación: `npm run build` y `npm run lint` desde `frontend/` terminaron con código 0; Vite advierte el tamaño del módulo 3D y lint advierte sobre `setState` en el efecto de `Globe.tsx`. Una ejecución inicial de build desde la raíz falló por ausencia de `package.json`; se repitió correctamente. No se han ejecutado pruebas de navegador ni lector de pantalla; siguen pendientes pruebas reales de interacción, accesibilidad, responsive y selección de hitos con datos definitivos.
