# Contribución y mantenimiento

Antes de realizar cambios, consulta la [instalación y desarrollo](docs/instalacion-desarrollo.md) y el estado del repositorio. Sigue los patrones existentes y usa commits descriptivos; el historial actual utiliza Conventional Commits. Los cambios de documentación afectados deben acompañar a la implementación en los mismos commits cuando corresponda.

## Lista de revisión para cada cambio

- [ ] Revisé si cambian funciones, pantallas, permisos o reglas y actualicé la guía de usuario y la referencia técnica afectadas.
- [ ] Revisé si cambian requisitos, comandos, variables, pruebas, despliegue, seguridad o respaldos y actualicé las guías correspondientes.
- [ ] Actualicé los enlaces del README si cambian los puntos de entrada; evité duplicar explicaciones entre documentos.
- [ ] Ejecuté `python3 scripts/check_doc_links.py` y las pruebas apropiadas; registré cualquier limitación.
- [ ] Si no fue necesaria ninguna actualización documental, expliqué brevemente por qué en la descripción del cambio o en el commit.

El comprobador revisa destinos de enlaces Markdown relativos en README, esta guía, AGENTS y `docs/`; no valida fragmentos, enlaces externos ni la exactitud del contenido. Se puede ejecutar desde cualquier directorio con la ruta al script. La revisión humana y la comprobación de ejemplos siguen siendo necesarias.

El repositorio no establece todavía un responsable, un canal de ayuda o de reporte privado de vulnerabilidades, ni una licencia. El propietario debe decidirlos antes de publicar esos datos; no se presupone que el código sea de licencia abierta. Consulta las [instrucciones para agentes](AGENTS.md).

## Criterios de documentación

Las guías toman como referencias orientativas [ISO/IEC/IEEE 15289:2019](https://www.iso.org/standard/74909.html), sobre información del ciclo de vida, e [ISO/IEC/IEEE 26514:2022](https://www.iso.org/obp/ui?_escaped_fragment_=iso%3Astd%3Aiso-iec-ieee%3A26514%3Aed-1%3Av1%3Aen), sobre información para usuarios. [Diátaxis](https://diataxis.fr/start-here/) ayuda a distinguir aprendizaje, tareas, referencia y explicación. Adoptar estas referencias no supone conformidad formal ni certificación.
