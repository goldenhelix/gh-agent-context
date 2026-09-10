# Task / Workflow validation schemas

JSON Schemas that validate `*.task.yaml`, `*.workflow.yaml`, `*.application.yaml`, and
`*.plugin.yaml` before you submit them:

- `task.json` — task definitions
- `workflow.json` — workflow (multi-stage) definitions
- `application.json` — application definitions
- `plugin.json` — plugin definitions

Extracted from a server's `/opt/backend/workspace-schemas/`. This repo pins no version — re-extract
per server release (`cp /opt/backend/workspace-schemas/*.json .`). When you're an agent running on
a server, prefer that server's own `/opt/backend/workspace-schemas/*.json` (version-matched); see
`../README.md`. The human-readable field reference is the server doc at
`/opt/frontend/docs/workspaces/automation/{task,workflow}-details.md` and the field notes in
[`../reference/task-workflow-authoring.md`](../reference/task-workflow-authoring.md).

These copies add `additionalProperties: false` for editor hinting; the server validates the same
schema without it, so an "additional properties" error usually means this copy is older than the
server, not that the key is unsupported.
