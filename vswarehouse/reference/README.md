# VS Warehouse reference — agent field notes

Operational notes distilled from real automation work on Golden Helix servers. These
**complement** (do not replace) the authoritative, version-matched product docs on the server
at `/opt/frontend/docs/` — they capture the gotchas those docs don't spell out.

| File | Read it when |
|---|---|
| [`agent-loop.md`](./agent-loop.md) | **Start here.** The run→poll→log→fix→rerun procedure for running tasks and workflows, plus task-path resolution. |
| [`environment.md`](./environment.md) | Writing a task step — container runtime, `/scratch`, `PYTHONPATH`, workspace secrets, path-resolution traps, image pulling. |
| [`task-workflow-authoring.md`](./task-workflow-authoring.md) | Authoring `*.task.yaml` / `*.workflow.yaml` — required fields, parameter types, stages, data passing, fan-out. |
| [`./gautil-client.md`](./gautil-client.md) | Driving the server from the shell — full command index + the run→poll→log loop. |
| [`ghclient-notes.md`](./ghclient-notes.md) | Driving the server from Python — auth precedence, catalog ids, `wait()` status strings. |
| [`pygautil-tsf.md`](./pygautil-tsf.md) | Reading/writing TSF tracks & catalogs — schema codes, `createTrack`/`convert`, multi-build. |

Authoritative sources on the server (prefer these when they disagree with anything here — they
are version-matched to the running build):
- Product docs: `/opt/frontend/docs/**/*.md` (search the `.md`, not the `.html`)
- Tool references: `/opt/frontend/docs/tools/{gautil,gautil-client,ghclient,pygautil}.md`
- Validation schemas: `/opt/backend/workspace-schemas/{task,workflow,application}.json`
- Built-in tasks: `/opt/backend/tasks/` (indexed in [`../../server-index/built-in-tasks.md`](../../server-index/built-in-tasks.md))
- Worked examples: `/opt/server_templates/` (indexed in [`../../server-index/server-templates.md`](../../server-index/server-templates.md))
