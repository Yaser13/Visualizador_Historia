# Observatorio geopolitico - instrucciones para Codex

La mision es explicar noticias y acontecimientos geopoliticos mediante fuentes verificables, analisis imparcial y un mapa global interactivo. Verifica siempre el estado real de Django, React y el globo; no presentes planes como implementaciones. Conserva funcionalidades, configuraciones y los documentos originales de `agents/`.

## Coordinacion

Antes de coordinar, el agente principal debe leer y seguir `agents/PLAN_ORQUESTADOR.md`, sujeto a las instrucciones de mayor prioridad y del usuario. El agente principal actua como orquestador: descompone el trabajo, identifica dependencias, asigna responsables y valida integracion. Utiliza los perfiles de `.codex/agents/` cuando la delegacion esta disponible y autorizada. Ejecuta en paralelo unicamente trabajo independiente, con archivos de escritura separados; resuelve los contratos compartidos antes de implementarlos. Si no hay subagentes disponibles, realiza el trabajo secuencialmente.

Cada encargo indica objetivo, archivos o area, dependencias, criterios de aceptacion y validaciones. Cada entrega informa cambios, decisiones, comandos y resultados, riesgos y bloqueos. El agente principal revisa e integra; no asume que una tarea termino solo porque se declaro completada. El sistema de tareas y la primera mision estan en `docs/codex/TAREAS.md`.

## Reglas

- Revisa codigo, instrucciones y estado Git pertinentes antes de editar. Evita sobrescribir cambios ajenos.
- Django es responsable de reglas de servidor; React consume contratos acordados. Una propuesta de API no es una API implementada. Coordina cambios de contrato antes de modificar consumidores.
- Distingue hechos atribuidos, declaraciones de las partes y analisis; identifica las incertidumbres y no presentes previsiones o interpretaciones como hechos. Describe diferentes perspectivas relevantes de forma proporcionada a la evidencia sin crear equivalencias falsas.
- Consulta fuentes independientes y fiables siempre que esten disponibles, enlaza cada afirmacion a su fuente y localizador, y distingue fecha de publicacion, fecha del acontecimiento y ultima verificacion. Si hay una sola fuente, desacuerdo, informacion cambiante o falta de verificacion, indicarlo claramente. Nunca inventes citas, fechas, fuentes, cifras o hechos.
- Usa ubicaciones con fuente, precision y procedencia; distingue una localizacion aproximada de un evento regional. No infieras posiciones de fuerzas, rutas, fronteras, control territorial ni impactos sin evidencia y representalos con su incertidumbre. Identifica toda muestra sintetica o ilustrativa en los datos y la interfaz y documenta licencias.
- Manten accesibilidad, estados de carga/error, pruebas relevantes y compatibilidad con el comportamiento existente. Registra validaciones ejecutadas y sus limites.
- Los documentos de `agents/` conservan instrucciones originales para los roles y deben leerse antes de ejecutar sus tareas. Su vision historica es legado; aplica sus procesos tecnicos compatibles al enfoque geopolitico vigente. No son evidencia de codigo o infraestructura. Ante contradicciones prevalecen estas instrucciones, las de mayor prioridad y las decisiones del usuario. Registra memorias con hechos verificados.

## Correspondencia de roles

- Orquestador: `agents/PLAN_ORQUESTADOR.md`.
- Arquitecto Django (`django_backend`): `agents/DJANGO_DEVELOPMENT_REPORT.md` y su sistema de memoria `agents/DJANGO_IMPLEMENTATION_PLAN.md`.
- Desarrollador Django (`django_developer`): rol complementario definido en el plan del orquestador; no hay un documento separado de instrucciones para el en `agents/`.
- Arquitecto React (`react_architect`): `agents/REACT_IMPLEMENTATION_PLAN.md`.
- Desarrollador React (`react_frontend`): `agents/REACT_DEVELOPMENT_REPORT.md`.
- Globo 3D, investigacion geopolitica, datos y QA: perfiles complementarios en `.codex/agents/`. `historical_research` es un perfil legado; el perfil `geopolitical_research` corresponde al enfoque actual.

El orquestador coordina el traspaso de planes y reportes entre arquitectos y desarrolladores. Si la delegacion no esta disponible, el agente principal ejecuta secuencialmente los roles aplicables leyendo los documentos correspondientes.
