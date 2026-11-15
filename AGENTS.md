# Historical Earth - instrucciones para Codex

La mision es explorar historia mediante documentacion verificable, Django, React y un globo 3D. El codigo de aplicacion aun no existe en la rama analizada: verifica siempre el estado real y no des por implementada una propuesta. Conserva funcionalidades, configuraciones y los documentos originales de `agents/`.

## Coordinacion

Antes de coordinar, el agente principal debe leer y seguir `agents/PLAN_ORQUESTADOR.md`, sujeto a las instrucciones de mayor prioridad y del usuario. El agente principal actua como orquestador: descompone el trabajo, identifica dependencias, asigna responsables y valida integracion. Utiliza los perfiles de `.codex/agents/` cuando la delegacion esta disponible y autorizada. Ejecuta en paralelo unicamente trabajo independiente, con archivos de escritura separados; resuelve los contratos compartidos antes de implementarlos. Si no hay subagentes disponibles, realiza el trabajo secuencialmente.

Cada encargo indica objetivo, archivos o area, dependencias, criterios de aceptacion y validaciones. Cada entrega informa cambios, decisiones, comandos y resultados, riesgos y bloqueos. El agente principal revisa e integra; no asume que una tarea termino solo porque se declaro completada. El sistema de tareas y la primera mision estan en `docs/codex/TAREAS.md`.

## Reglas

- Revisa codigo, instrucciones y estado Git pertinentes antes de editar. Evita sobrescribir cambios ajenos.
- Django es responsable de reglas de servidor; React consume contratos acordados. Una propuesta de API no es una API implementada. Coordina cambios de contrato antes de modificar consumidores.
- Distingue hechos documentados, interpretaciones, incertidumbres y datos sinteticos. Nunca inventes citas, fuentes, fechas ni limites territoriales; documenta procedencia y licencias.
- Las geometrias y fechas de demostracion deben identificarse como ilustrativas en los datos y en la interfaz. No presentar una frontera sintetica como representacion historica.
- Manten accesibilidad, estados de carga/error, pruebas relevantes y compatibilidad con el comportamiento existente. Registra validaciones ejecutadas y sus limites.
- Los documentos de `agents/` son las instrucciones originales para los roles correspondientes y deben leerse antes de ejecutar sus tareas. No son evidencia de que exista codigo o infraestructura: verifica el estado real. Ante contradicciones prevalecen las instrucciones de mayor prioridad y del usuario. Registra memorias con hechos verificados, sin presentar suposiciones como hechos.

## Correspondencia de roles

- Orquestador: `agents/PLAN_ORQUESTADOR.md`.
- Arquitecto Django (`django_backend`): `agents/DJANGO_DEVELOPMENT_REPORT.md` y su sistema de memoria `agents/DJANGO_IMPLEMENTATION_PLAN.md`.
- Desarrollador Django (`django_developer`): rol complementario definido en el plan del orquestador; no hay un documento separado de instrucciones para el en `agents/`.
- Arquitecto React (`react_architect`): `agents/REACT_IMPLEMENTATION_PLAN.md`.
- Desarrollador React (`react_frontend`): `agents/REACT_DEVELOPMENT_REPORT.md`.
- Globo 3D, investigacion historica, datos y QA: perfiles complementarios en `.codex/agents/`.

El orquestador coordina el traspaso de planes y reportes entre arquitectos y desarrolladores. Si la delegacion no esta disponible, el agente principal ejecuta secuencialmente los roles aplicables leyendo los documentos correspondientes.
