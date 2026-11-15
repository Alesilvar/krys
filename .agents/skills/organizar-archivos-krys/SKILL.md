---
name: organizar-archivos-krys
description: Revisa o mejora la organización de archivos del proyecto Krys, considerando sus convenciones Django, React y Vite. Úsala cuando se solicite evaluar, proponer o implementar una reorganización de su estructura.
---

# Organizar archivos de Krys

Antes de proponer o realizar cambios, revisa las instrucciones aplicables, el estado del repositorio, su estructura, configuración, documentación y los archivos relacionados con la solicitud. Distingue las convenciones documentadas de Django, React y Vite de las decisiones particulares de Krys; presenta estas últimas como recomendaciones, no como requisitos de los frameworks.

Aplica estos criterios según el problema observado:

- Conserva `config/` para la configuración de Django y `records/` como aplicación principal, salvo que exista una razón concreta para cambiarlos. No crees aplicaciones ni carpetas solo por seguir un esquema ideal.
- Divide módulos y pruebas extensos por responsabilidades o comportamientos cuando mejore su mantenimiento. Comprueba los usos y dependencias antes de mover código; no cambies el comportamiento como parte de una reorganización sin que se haya solicitado.
- Organiza React por funcionalidades y componentes compartidos cuando el crecimiento lo justifique. `frontend/src/` es la fuente y `static/react/app.js` es el resultado compilado versionado: regenera y comprueba el resultado cuando corresponda.
- Conserva las migraciones existentes y verifica las importaciones, el descubrimiento de pruebas, las rutas y las referencias a plantillas y recursos afectados. Considera tanto `manage.py test` como las pruebas independientes pertinentes.
- Revisa y actualiza la documentación afectada conforme a `AGENTS.md` y `CONTRIBUTING.md`; ejecuta sus comprobaciones y las pruebas pertinentes. Respeta las instrucciones, permisos y alcance de la solicitud: invocar esta skill no autoriza por sí solo a modificar archivos.

Para fundamentar una recomendación, consulta cuando sea pertinente las guías oficiales de [aplicaciones Django](https://docs.djangoproject.com/en/5.2/ref/applications/), [aplicaciones reutilizables Django](https://docs.djangoproject.com/en/5.2/intro/reusable-apps/), [componentes React](https://react.dev/learn/importing-and-exporting-components), [integración de Vite con un backend](https://vite.dev/guide/backend-integration) y [organización de pruebas con pytest](https://docs.pytest.org/en/stable/explanation/goodpractices.html).
