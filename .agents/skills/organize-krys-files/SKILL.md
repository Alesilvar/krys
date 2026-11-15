---
name: organize-krys-files
description: Review or improve file organization in the Krys project using its Django, React, and Vite conventions. Use when asked to assess, propose, or implement changes to the project structure.
---

# Organize Krys files

Before proposing or making changes, inspect applicable instructions, repository status, structure, configuration, documentation, and files relevant to the request. Distinguish documented Django, React, and Vite conventions from Krys-specific decisions; present the latter as recommendations rather than framework requirements.

Apply these criteria as appropriate to the observed problem:

- Keep `config/` for Django configuration and `records/` as the main application unless there is a concrete reason to change them. Do not create applications or directories solely to match an idealized structure.
- Split large modules and tests by responsibility or behavior when this improves maintainability. Check usages and dependencies before moving code; do not change behavior as part of a reorganization unless requested.
- Organize React by feature and shared components when growth warrants it. `frontend/src/` is the source and `static/react/app.js` is the tracked build output: regenerate and verify it when appropriate.
- Preserve existing migrations and verify imports, test discovery, routes, and references to affected templates and assets. Consider both `manage.py test` and relevant standalone tests.
- Review and update affected documentation in accordance with `AGENTS.md` and `CONTRIBUTING.md`; run their checks and relevant tests. Respect applicable instructions, permissions, and the scope of the request: invoking this skill does not itself authorize file changes.

When relevant, support recommendations with the official guides to [Django applications](https://docs.djangoproject.com/en/5.2/ref/applications/), [reusable Django applications](https://docs.djangoproject.com/en/5.2/intro/reusable-apps/), [React components](https://react.dev/learn/importing-and-exporting-components), [Vite backend integration](https://vite.dev/guide/backend-integration), and [pytest test organization](https://docs.pytest.org/en/stable/explanation/goodpractices.html).
