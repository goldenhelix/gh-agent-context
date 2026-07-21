# Task / Workflow validation schemas

JSON Schemas that validate `*.task.yaml`, `*.workflow.yaml`, and `*.application.yaml` before you
submit them:

- `task.json` — task definitions
- `workflow.json` — workflow (multi-stage) definitions
- `application.json` — application definitions

Extracted from a server's `/opt/backend/workspace-schemas/`. This repo pins no version — re-extract
per server release (`cp /opt/backend/workspace-schemas/*.json .`). When you're an agent running on
a server, prefer that server's own `/opt/backend/workspace-schemas/*.json` (version-matched); see
`../README.md`. The human-readable field reference is the server doc at
`/opt/frontend/docs/workspaces/automation/{task,workflow}-details.md` and the field notes in
[`../reference/task-workflow-authoring.md`](../reference/task-workflow-authoring.md).
