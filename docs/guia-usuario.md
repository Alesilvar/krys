# Guía de usuario

KS mantiene cartas CPC, respuestas AAM y registros de equipos. Inicia sesión con una cuenta proporcionada por el administrador; la pantalla principal muestra el historial y los indicadores.

## Consultar y exportar

En **Inicio**, consulta la situación actual, las acciones rápidas, el gráfico de equipos activos por tipo y hasta cinco cartas pendientes, ordenadas de la más antigua a la más reciente. Usa **Ver todas las pendientes** para abrir la lista completa. En escritorio, el botón de la barra lateral permite reducirla a iconos o volver a expandirla; en móvil, usa el menú superior. El gráfico incluye equipos con estado activo y al menos una presentación o movimiento; excluye los equipos sin historial y agrupa los que no tienen tipo por separado. «En uso con aprobación» cuenta equipos con tipo, alguna evaluación aprobada y estado activo o retiro solicitado, por lo que puede diferir del gráfico.

En **Registros**, consulta las métricas históricas y busca por placa, carta o tipo; también puedes filtrar por resultado SST y estado operativo. Pulsa **Buscar** para aplicar los filtros y **Limpiar** para retirarlos. El panel indica cuántos resultados coinciden; abre **Ver detalle** para consultar la carta, el trámite, los documentos y las acciones disponibles. Usa **CSV** o **Excel** para exportar todos los resultados filtrados. Las evaluaciones observadas son históricas y pueden haberse subsanado. Los indicadores resumen el conjunto de datos, no solo la selección.

En **Cartas**, busca por número o equipo y filtra por respuesta pendiente o respondida; cada expediente resume la fecha y el estado de respuesta de su última carta CPC; ábrelo para ver cartas, equipos y PDF disponibles.

Si una pantalla no carga, comprueba la conexión y utiliza **Volver a intentar**. Si falla una operación en un formulario, revisa el mensaje y vuelve a intentarla. Los estados se identifican con texto además de color.

## Cargar cartas PDF

1. Con permiso de edición, abre **Cargar cartas**, selecciona una o varias cartas CPC y AAM y pulsa **Extraer y revisar**. Incluye documentos anteriores cuando sean necesarios para establecer la cadena. Si un PDF no contiene texto seleccionable, KS intenta reconocerlo mediante OCR en español. Revisa los datos extraídos: la calidad del escaneo puede afectar el resultado. Si el PDF contiene texto seleccionable, se usa ese texto. Se admiten hasta 20 archivos por carga, cada uno un PDF válido de hasta 10 MB. Con JavaScript activo puedes revisar los archivos seleccionados y quitar alguno antes de extraer.
2. Compara los datos extraídos y las advertencias con los documentos originales. Introduce la fecha de recepción de cada CPC y, si corresponde, el dato adicional de cada equipo.
3. Si se indica un conflicto con una evaluación existente, revisa ambos valores y marca la casilla de reemplazo solo si deseas sustituirla. Si no la marcas, la evaluación actual se conserva.
4. Pulsa **Guardar datos**. La vista previa no guarda registros hasta su confirmación. Si caduca o aparece un error, vuelve a cargar y revisar los archivos.

Si hay un dato extraído incorrectamente, no lo des por válido: revisa los documentos y, tras guardar, usa las opciones de edición correspondientes. Una respuesta de desmovilización necesita su solicitud referenciada disponible en la carga o en los archivos ya registrados.

## Ingreso y edición manual

En **Ingreso manual**, completa los campos marcados como obligatorios en las secciones de carta CPC y equipo. El formulario incluye ejemplos y explica los campos de la respuesta AAM. Para una subsanación indica la respuesta AAM anterior; si hay resultado SST, proporciona también el número y la fecha de la respuesta. Adjuntar PDF es opcional. Guarda el registro; si la carta ya existe, se agrega otra fila a esa carta.

En **Registros**, usa **Editar** para una presentación. En **Cartas** puedes editar la carta o el equipo de una desmovilización. Los cambios en datos compartidos de una carta afectan a todos sus equipos. Las validaciones se muestran en el formulario; corrige los campos y vuelve a guardar.

## Estado y empates

El resultado SST y el estado operativo son datos distintos. El equipo puede estar activo, con retiro solicitado, retirado o **Por revisar**. Cuando una aprobación y un retiro empatan en la fecha más reciente, se excluye del inventario en uso. Una persona con permiso de edición puede pulsar **Revisar empate**, comparar los eventos y elegir cuál ocurrió después; la decisión queda auditada y se invalida si cambian los eventos o sus fechas. Las reglas se describen en la [referencia técnica](referencia-tecnica.md).

## Permisos y eliminación

Las cuentas nuevas pueden consultar y exportar. Un superusuario asigna desde `/admin/` el grupo **Edición** para crear y modificar, o **Administración de registros** para modificar y eliminar; **Consulta** identifica opcionalmente a quienes solo leen. Los superusuarios tienen todos los permisos. Las cuentas existentes antes de la migración de permisos conservan acceso completo. Los PDF requieren autenticación.

En **Cartas**, abre el expediente y usa **Eliminar esta carta** en la carta CPC correspondiente. La acción requiere permiso de administración de registros y muestra una confirmación con las cantidades y los documentos afectados. Borra definitivamente la carta CPC, sus presentaciones y movimientos, la respuesta vinculada y sus PDF disponibles. Las subsanaciones posteriores se conservan, pero dejan de estar vinculadas a esa respuesta. Consulta con el administrador antes de confirmar si necesitas recuperar información.
