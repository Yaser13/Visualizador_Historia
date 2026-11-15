# SISTEMA DE MEMORIA PERSISTENTE DEL ARQUITECTO DJANGO

## 1. Objetivo

Mantener una memoria técnica persistente del proyecto para evitar análisis repetitivos y preservar el conocimiento acumulado entre sesiones.

La memoria será la fuente principal de contexto del agente.

**Archivo obligatorio:**

`docs/architecture/DJANGO_ARCHITECT_MEMORY.txt`

El agente debe consultar este archivo antes de realizar cualquier tarea arquitectónica.

No debe analizar todo el proyecto nuevamente cuando la memoria existente sea suficiente y esté actualizada.

## 2. Inicialización

### Primera ejecución

Si el archivo de memoria no existe:

1. Analizar la estructura del proyecto una sola vez.
2. Identificar las aplicaciones Django y sus responsabilidades.
3. Registrar la arquitectura y las dependencias principales.
4. Identificar modelos, relaciones, APIs, servicios y procesos críticos.
5. Registrar mecanismos de autenticación, autorización y seguridad.
6. Identificar infraestructura, tareas asíncronas y componentes de escalabilidad.
7. Registrar los problemas técnicos conocidos.
8. Crear `DJANGO_ARCHITECT_MEMORY.txt`.
9. Guardar la fecha de análisis y el identificador del commit analizado, si existe.

### Ejecuciones posteriores

Cuando exista el archivo:

1. Leer la memoria.
2. Comprender el estado conocido del proyecto.
3. Identificar los módulos relacionados con la solicitud.
4. Comprobar si la memoria de esos módulos sigue vigente.
5. Inspeccionar únicamente los archivos necesarios para confirmar información crítica o resolver diferencias.
6. Diseñar la solución.
7. Generar el plan técnico.
8. Actualizar la memoria con la nueva información verificada.

**Está prohibido ejecutar auditorías completas del repositorio por defecto en cada solicitud.**

Se permite un nuevo análisis general únicamente cuando exista una razón justificada, como una refactorización estructural, una memoria inexistente o una inconsistencia significativa que no pueda resolverse mediante inspección localizada.

## 3. Estructura obligatoria de memoria

El archivo TXT deberá incluir estas secciones:

### [01] IDENTIDAD DEL PROYECTO
- Nombre y propósito.
- Stack tecnológico.
- Versiones verificadas.
- Dependencias principales.
- Convenciones de desarrollo.

### [02] ARQUITECTURA GENERAL
- Estilo arquitectónico.
- Organización de aplicaciones.
- Responsabilidades de los módulos.
- Dependencias internas.
- Patrones utilizados.

### [03] MODELOS Y BASE DE DATOS
- Entidades importantes.
- Relaciones.
- Restricciones de integridad.
- Índices relevantes.
- Reglas de concurrencia.

### [04] APIs Y SERVICIOS
- Endpoints principales.
- Servicios internos.
- Integraciones externas.
- Contratos relevantes.
- Autorizaciones.

### [05] SEGURIDAD
- Mecanismos existentes.
- Controles implementados.
- Riesgos conocidos.
- Vulnerabilidades pendientes.
- Decisiones de seguridad.

Nunca almacenar contraseñas, tokens, claves privadas, secretos o información personal innecesaria.

### [06] RENDIMIENTO Y ESCALABILIDAD
- Cuellos de botella conocidos.
- Caché.
- Procesos asíncronos.
- Colas.
- Limitaciones técnicas.
- Mediciones disponibles.
- Oportunidades de elasticidad.

### [07] DECISIONES ARQUITECTÓNICAS
Para cada decisión registrar:
- Identificador.
- Fecha.
- Problema.
- Alternativas consideradas.
- Decisión adoptada.
- Justificación.
- Componentes afectados.
- Estado actual.

### [08] HISTORIAL DE CAMBIOS
Registrar incrementalmente:
- Fecha.
- ID del plan.
- Cambio propuesto.
- Cambio implementado y verificado.
- Archivos afectados.
- Resultado de pruebas.
- Riesgos pendientes.

Distinguir expresamente entre cambios planificados, implementados y validados.

### [09] ESTADO ACTUAL DEL PROYECTO
- Funcionalidades confirmadas.
- Funcionalidades en desarrollo.
- Planes pendientes.
- Problemas abiertos.
- Deuda técnica.
- Próximas prioridades.

### [10] CONTEXTO PARA PRÓXIMAS SESIONES
- Qué debe conocer el arquitecto.
- Qué decisiones no debe reinterpretar sin fundamento.
- Qué elementos requieren validación.
- Qué trabajo está pendiente.
- Qué información podría haber quedado desactualizada.

### [11] CONTROL DE VIGENCIA
Registrar:
- Fecha de última actualización.
- Commit de referencia.
- Archivos o módulos cubiertos.
- Fuente de cada actualización relevante.
- Información confirmada.
- Información potencialmente obsoleta.

## 4. Política de actualización incremental

Actualizar la memoria cuando:

- Se confirme una nueva decisión arquitectónica.
- Se apruebe un plan.
- El desarrollador entregue una implementación verificable.
- Se introduzca o elimine un módulo.
- Cambien modelos, APIs o integraciones.
- Se corrija una vulnerabilidad.
- Se descubra una limitación importante.
- Se valide una mejora de rendimiento.
- Cambie una dependencia o convención relevante.

No actualizar la memoria con suposiciones presentadas como hechos.

No reemplazar automáticamente el estado real del sistema con lo descrito en un plan.

No duplicar el historial completo cada vez que se produzca una modificación.

Conservar un resumen acumulativo compacto y un historial cronológico de decisiones significativas.

## 5. Detección de cambios

Cuando el repositorio utilice Git:

- Consultar el commit registrado en la memoria.
- Compararlo con el commit actual.
- Revisar los archivos modificados desde ese punto.
- Determinar cuáles afectan a la tarea y al conocimiento almacenado.
- Actualizar únicamente las secciones pertinentes.

Utilizar comparaciones incrementales siempre que sea posible.

Si los commits no tienen relación directa, el historial no está disponible o existen modificaciones sin confirmar, no asumir que una comparación de Git ofrece una visión completa.

En esos casos efectuar inspecciones localizadas y marcar las secciones no verificadas.

La memoria reduce la necesidad de exploración, pero no sustituye la comprobación del código cuando una decisión depende de su estado actual.

## 6. Coordinación con el agente desarrollador

Cada plan debe solicitar al agente desarrollador un reporte estructurado con:

- ID de tareas ejecutadas.
- Archivos modificados.
- Cambios realizados.
- Migraciones aplicadas o pendientes.
- Pruebas ejecutadas y resultados.
- Desviaciones respecto del diseño.
- Problemas detectados.
- Evidencia de implementación.

El arquitecto utilizará este reporte para actualizar su memoria.

Un cambio reportado pero no comprobado debe quedar marcado como `REPORTADO_NO_VERIFICADO`.

Un cambio confirmado mediante evidencia suficiente podrá registrarse como `VERIFICADO`.

## 7. Reglas de eficiencia

- Leer la memoria antes de inspeccionar código.
- Evitar búsquedas globales innecesarias.
- Limitar las lecturas a los componentes relacionados con la solicitud.
- Reutilizar decisiones arquitectónicas todavía válidas.
- Evitar volver a documentar información sin cambios.
- Preferir diferencias incrementales a auditorías completas.
- Mantener el contexto resumido para reducir consumo de tokens.
- Conservar referencias a archivos para facilitar verificaciones futuras.

Si se necesita una auditoría completa, justificar por qué la memoria y una inspección localizada resultan insuficientes.

## 8. Integridad de la memoria

La memoria debe ser precisa, consistente y recuperable.

Antes de actualizarla:

1. Comprobar que la información nueva no contradiga hechos confirmados sin explicación.
2. Conservar las decisiones históricas relevantes.
3. Actualizar el estado vigente.
4. Registrar las novedades.
5. Mantener referencias al código o evidencia.
6. Evitar guardar datos sensibles.

Si se identifica una contradicción, marcarla como pendiente de resolución.

No inventar contexto para completar secciones vacías.

**REGLA FUNDAMENTAL:**

La memoria es la fuente principal de contexto operativo del arquitecto, mientras que el código, las pruebas y la infraestructura son las fuentes de verdad sobre la implementación real.

El objetivo es minimizar análisis repetitivos sin comprometer la precisión del diseño.
