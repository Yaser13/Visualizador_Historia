# Contratos de coordinacion

El orquestador asigna cada tarea con ID, resultado, alcance y archivos, dependencias, prioridad, criterios de aceptacion y validaciones. Cada agente devuelve cambios y archivos, decisiones y contratos, comandos y resultados, riesgos, incertidumbres y bloqueos. Los archivos compartidos tienen un unico responsable de escritura; los demas proponen cambios. La coordinacion no reemplaza las instrucciones originales aplicables en agents/.

## Arquitectura e implementacion

- Django: django_backend sigue los documentos originales de arquitectura y memoria, define y entrega un plan y contrato verificables a django_developer. Este implementa y devuelve reporte. Una propuesta no es una API existente.
- React: react_architect sigue el plan original de arquitectura, disena accesibilidad y contrato de integracion y entrega el plan a react_frontend. Este sigue el documento original de desarrollo, implementa y devuelve reporte.
- Globo: globe_3d acuerda con react_architect la interfaz de componentes y con data_engineer el formato y sistema de coordenadas; informa limitaciones, rendimiento y liberacion de recursos.
- Investigacion: historical_research devuelve fuentes localizables, licencias conocidas, afirmaciones, incertidumbre y huecos. No presenta datos sinteticos como evidencia.
- Datos: data_engineer entrega esquema versionado, convencion de fechas y coordenadas, metadatos de procedencia y validaciones; distingue demostracion de datos verificados.
- QA: qa_testing recibe criterios y versiones integradas, verifica comportamiento observable y reporta comandos, resultados y pruebas pendientes.

El orquestador acepta una entrega cuando cumple sus criterios, resuelve los bloqueos y tiene evidencia de validacion. Las dependencias se desbloquean solo despues de revisar los contratos necesarios; una aprobacion tecnica de un agente no sustituye los permisos o instrucciones del usuario.
