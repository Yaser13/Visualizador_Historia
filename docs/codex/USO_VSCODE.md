# Uso de Codex en VS Code

1. Abre la carpeta raiz del repositorio en VS Code y confia en el proyecto solo si corresponde. Abre la extension de Codex e inicia una conversacion nueva para cargar la configuracion del proyecto.
2. Pide, por ejemplo: Actua como orquestador, revisa AGENTS.md y docs/codex/TAREAS.md, y delega las tareas independientes de la primera mision a los agentes especializados; integra y valida sus resultados.
3. Revisa el progreso y los cambios propuestos; asigna tareas secuenciales cuando compartan archivos o dependan de contratos pendientes. Los subagentes heredan permisos del hilo principal. El perfil orchestrator tambien se puede solicitar como subagente, pero AGENTS.md indica al hilo principal que coordine.
4. En el terminal integrado, comprueba la instalacion con `codex --version` y la configuracion con `codex --strict-config doctor`. Las opciones y disponibilidad pueden depender de la version y del entorno; si no aparecen subagentes, usa un nuevo hilo y revisa el estado de la funcion con `codex features list`.

Referencia: [operaciones multiagente de Codex](https://learn.chatgpt.com/docs/agent-configuration/subagents). Los perfiles leen los documentos originales de `agents/` correspondientes a cada rol. Sus planes y memorias propuestas no prueban que exista la aplicacion. Consulta la correspondencia en `AGENTS.md`.

Codex solo carga la configuracion local de proyectos de confianza. Si no aparecen los perfiles, comprueba que abriste esta carpeta local y marca el proyecto como confiable en Codex cuando estes conforme; reinicia la conversacion y vuelve a comprobar. La confianza del proyecto de VS Code y la configuracion de confianza de Codex pueden ser controles distintos. La carpeta `.codex` puede estar oculta por filtros del explorador.
