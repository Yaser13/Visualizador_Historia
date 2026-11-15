# Plan del observatorio geopolítico: de una noticia a información verificable

Fecha: 2026-11-15. Estado: plan de evolución; las capacidades propuestas no se consideran implementadas hasta revisar código y pruebas. La solicitud inicial del usuario puede ser un enlace, texto o referencia proporcionada manualmente. La finalidad es facilitar el análisis informado, no declarar una versión definitiva o automáticamente imparcial de los hechos.

## Estado verificado al iniciar este plan

`backend/stories/news_data.py` contiene una instantánea estática de la COP31; `views.py` la entrega en `GET /api/stories/geopolitica/`. React muestra noticia, análisis, fuentes y ubicación. La fecha de corte está indicada y no hay recolección ni actualización automática. La configuración revisada usa SQLite para desarrollo; los datos de la noticia de la API proceden de código, no de un flujo de ingesta automatizado. Se está desarrollando en paralelo un modelo de base de datos: verificar su estado y migraciones antes de atribuirle funcionalidades. No se han identificado proveedores de búsqueda ni licencias de contenido acordados.

## Resultado deseado y límites editoriales

Para cada noticia, permitir consultar qué se afirma, quién lo afirma, dónde y cuándo, qué fuentes lo sustentan o contradicen, qué actores y acciones aparecen, qué objetivos se les atribuyen y qué efectos documentados se conocen. Diferenciar hecho corroborado, declaración atribuida, análisis, previsión y dato sin confirmar. Los datos desconocidos o todavía no evaluados deben quedar como desconocidos, no completarse mediante inferencias.

Una valoración positiva o negativa **no es un atributo objetivo y universal de la noticia**: conservarla solo si es una evaluación atribuida o un análisis explícito, indicando perspectiva, objeto, criterios, evidencia, fecha e incertidumbre; permitir valoraciones distintas o ausencia de ellas. «Responsable» requiere especificar si se trata de autoría, participación, responsabilidad declarada, presunta o establecida, por quién y con qué fundamento. Un efecto presunto no equivale a causalidad demostrada. Los objetivos se atribuyen a quien los declara, no se infieren de su conducta.

## Flujo propuesto

1. **Recepción:** registrar URL, referencia o texto aportado, fecha, idioma y procedencia; almacenar copia solo cuando derechos y configuración lo permitan. No publicar automáticamente.
2. **Identificación y búsqueda:** proponer términos a partir de actores, lugar, fecha y acción; consultar proveedores de búsqueda compatibles cuando se seleccionen y autoricen. Registrar consulta, proveedor, fecha y resultados; filtrar duplicados. Una búsqueda limitada no acredita exhaustividad ni independencia.
3. **Fuentes candidatas:** recoger metadatos, fuente primaria o secundaria, fecha de publicación/actualización conocida, acceso y derechos; conservar URL, versión o hash cuando proceda. Establecer independencia por cadena editorial/procedencia, no solo por dominios diferentes. Si no puede consultarse una fuente, registrar el límite.
4. **Extracción:** separar afirmaciones atómicas de sus interpretaciones; registrar fuente, localizador, método, fecha de consulta y fragmento breve solo si está permitido. Capturar entidades, acciones, objetivos declarados, efectos y ubicaciones con su precisión, como candidatos por revisar. No fabricar citas ni tratar texto generado como fuente.
5. **Contraste y revisión:** enlazar evidencias que apoyan, contradicen o contextualizan cada afirmación. Una persona revisora resuelve identidad de actores y duplicados, verifica fechas, lugar, roles y representación, registra desacuerdos y estado (`pendiente`, `en revisión`, `respaldada`, `disputada`, `incierta`, `rechazada`). La falta de contraste queda visible. La confianza y neutralidad son evaluaciones justificadas, no garantías automáticas.
6. **Publicación y visualización:** únicamente mostrar registros revisados según la política editorial acordada; visualizar iconos que indiquen categoría, no hechos no documentados. Enlazar desde el mapa al detalle, las fuentes, la fecha de corte y la precisión. No representar frentes, rutas, control, zonas afectadas ni fuerzas sin fuente y alcance temporal y espacial apropiados.
7. **Seguimiento:** conservar versiones de fuentes y afirmaciones, registrar fecha de última comprobación y próxima revisión cuando exista; no presentar contenido estático como noticia en directo. Una nueva fuente o corrección crea una nueva versión y puede cambiar el estado o retirar una visualización, sin borrar el historial. Las frecuencias y proveedores quedan por decidir; si falla una actualización se muestra la última verificación y el error operativo.

## Información granular y relaciones previstas

| Elemento | Campos y vínculos mínimos | Restricción editorial |
|---|---|---|
| Ingesta | entrada, tipo, fecha, estado, origen y errores | Una entrada no equivale a noticia verificada. |
| Fuente y versión | título, autor/medio, URL, fecha de publicación y modificación si se conocen, consulta, licencia o desconocida, hash/versionado cuando proceda | Cada versión tiene procedencia; no almacenar contenido íntegro sin derechos. |
| Acontecimiento | título, tipo, categorías, fecha o intervalo y precisión, estado editorial, fechas de creación y actualización | Separa fecha del evento de publicación y consulta; admite faltantes. |
| Afirmación y evidencia | texto o contenido estructurado, tipo, atribución, estado; relaciones a fuentes con localizador y relación apoya/contradice/contextualiza | Cada afirmación que se publique necesita evidencia revisada; el desacuerdo se conserva. |
| Actor y participación | identidad y tipo (país, organización, persona u otro), rol en acontecimiento, periodo y evidencia | Roles plurales y contextualizados; no imponer culpabilidad. |
| Acción y objetivo | actor, acción, objeto, fecha/alcance, fuentes; objetivo declarado con autor y evidencia | Separar acción reportada de finalidad declarada e interpretación. |
| Efecto y valoración | actor o área afectada, efecto atribuido, momento y precisión; valoración opcional con perspectiva y justificación | Puede ser incierto, disputado o desconocido; no forzar polaridad ni causa. |
| Lugar | nombre, tipo, geometría o coordenadas opcionales, sistema, precisión, fuente y vigencia | Punto aproximado no significa extensión, frontera ni territorio controlado. |
| Análisis y revisión | texto, autor/método, fecha de corte, hipótesis, evidencia enlazada, estado, revisión y versiones | Distinguir interpretación de hechos, y mostrar incertidumbre y límites. |

Los nombres y relaciones anteriores son conceptos de dominio, no nombres de modelos o endpoints confirmados. Adoptar los modelos efectivamente implementados tras revisarlos; documentar cualquier diferencia en un contrato versionado antes de integrar React. Definir claves estables, índices y restricciones de unicidad según necesidades verificadas; proteger referencias al borrar o versionar registros. Usar transacciones para cambios relacionados y evitar duplicaciones por reintentos. SQLite sirve para desarrollo inicial; evaluar PostgreSQL en función de concurrencia, escala y operaciones geográficas reales, sin prometer escalabilidad antes de medirla.

## Ingesta y búsqueda: arquitectura pendiente

Django debe recibir solicitudes, conservar estados y aplicar reglas; React debe mostrar progreso, errores y revisión. Para trabajo largo, diseñar una cola y trabajadores solo al introducir consultas remotas; sus trabajos necesitan límites de tiempo, reintentos acotados, deduplicación, auditoría y posibilidad de reanudar. Los conectores deben tener una interfaz común que devuelva resultados con metadatos verificables, sin asumir que un servicio concreto existe ni contratar servicios con costo. Evaluar condiciones de uso, robots, reproducción de contenido y atribución antes de integrar un proveedor. Al abrir enlaces aportados por usuarios, validar protocolo, redirecciones, direcciones de destino y tamaños para impedir acceso a redes internas y descargas abusivas; tratar texto y archivos como no confiables. No exponer credenciales al cliente.

Una primera versión útil puede aceptar referencias y cargar afirmaciones manualmente mediante administración restringida, con revisión humana; la búsqueda automatizada se agrega cuando haya proveedor y políticas verificadas. El contrato OpenAPI, autenticación, permisos de edición y mecanismo de revisión deben acordarse entre backend y frontend antes de crear o modificar consumidores. Definir primero lectura de noticia detallada, luego propuestas de ingesta y revisión; los endpoints y estados concretos aún no están implementados por este plan.

## Secuencia y criterios de aceptación

| Paso | Dependencias | Entrega y validación |
|---|---|---|
| 1. Modelo y migraciones | Contratos de evidencia y diseño Django | Guardar noticia, fuentes, actores, afirmaciones, relaciones, fechas y lugares según alcance implementado; probar restricciones, nulos, integridad, rollback y persistencia. |
| 2. COP31 desglosada | Paso 1 y ficha documental revisada | Cargar de forma reproducible y sin duplicados únicamente afirmaciones y roles documentados; revisar locatores, fechas, incertidumbres y procedencia. No asignar efectos o polaridad sin fundamento. |
| 3. Lectura y mapa | Paso 2; contrato estable | API documentada y probada; interfaz muestra fuentes, perspectiva y precisión; ausencia de datos no produce iconos o posiciones ficticias. Comprobar cargas, errores, teclado y móvil. |
| 4. Recepción y revisión manual | Permisos y contrato acordados | Registrar propuesta, vincular fuentes y revisar sin publicación automática; pruebas de autorización, validación y transiciones. |
| 5. Búsqueda asistida | Pasos 2–4; proveedor, licencias y acceso acordados | Guardar consulta y resultados con procedencia; controlar fallos/duplicados y exigir revisión; probar fuentes contradictorias y resultados vacíos. |
| 6. Actualización/versionado | Reglas editoriales y operación definidas | Actualizar sin sobrescribir evidencia, mostrar fecha de corte y corregir o retirar representación cuando cambie; probar reintentos y fallos. |

Al aceptar cada paso, registrar archivos, comandos y resultados realmente ejecutados, junto con limitaciones. Mantener la noticia estática y la ruta previa compatibles hasta acordar una transición; el hecho de crear tablas no significa que la API ya las consulte. No introducir despliegue ni publicación externa dentro de este plan.

## Riesgos y decisiones pendientes

- **Fuentes escasas o dependientes:** informar límites y contradicciones; una fuente institucional no siempre es independiente de un actor involucrado.
- **Desactualización:** fecha de corte visible, historial y revisión; ningún sistema de actualización existe todavía.
- **Opinión presentada como hecho:** separar tipo, autor, perspectiva y fuente; no calcular automáticamente una polaridad universal.
- **Geografía engañosa:** precisión y procedencia para cada representación; abstenerse de dibujar áreas sin respaldo.
- **Derechos y acceso:** guardar enlaces y metadatos; revisar permisos y restricciones antes de recopilar textos o imágenes.
- **Costos y proveedor:** comparar cobertura, licencias, límites y precio antes de elección; el trabajo local actual no incorpora servicios externos.
