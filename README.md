# gh-agent-context

Agent grounding for working on a **Golden Helix VS Warehouse** server. This repo is checked out
on the server (inside a workspace's `Automation/` tree, or alongside it) so that an AI agent
running there has everything it needs to use the platform's tools correctly: the CLI/SDK
references, the task/workflow authoring conventions, the operational gotchas, and pointers to the
version-matched docs, schemas, and worked examples that already live on the box.

**Start at [`CLAUDE.md`](./CLAUDE.md).**

## What's here

```
CLAUDE.md                     Orientation: GH_ env vars, the agentic loop, the map, server layout.
ROADMAP.md                    Planned areas (VarSeq, VS Pipeline, VSClinical scripting, reports).
vswarehouse/
  README.md                   Subtree landing page + source-of-truth rule (server-local wins).
  reference/                  Agent field notes — the how-to knowledge + gotchas:
    README.md                   index of the field notes
    agent-loop.md               the run→poll→log→fix→rerun procedure (start here)
    gautil-client.md            the gautil client command index + reading run output
    task-workflow-authoring.md  writing *.task.yaml / *.workflow.yaml
    environment.md              task runtime: /scratch, PYTHONPATH, secrets, images, path traps
    ghclient-notes.md           the Python SDK
    pygautil-tsf.md             reading/writing TSF tracks & catalogs
  examples/                   Curated, runnable task/workflow/plugin definitions to copy.
  schemas/                    Static task/workflow/application JSON Schemas (fallback).
  api/                        OpenAPI / REST specs for the workspace + admin APIs.
server-index/                 Searchable indexes of what's installed ON this server:
    built-in-tasks.md           /opt/backend/tasks (System/ tasks)
    server-templates.md         /opt/server_templates example tasks/workflows/apps
    generate-index.py           Regenerate the two indexes above.
sandbox/                      Copies of template tasks to practice running & fixing end-to-end.
```

## Design principles
- **The live server is the source of truth.** This repo points at `/opt/frontend/docs`,
  `/opt/backend/workspace-schemas`, `/opt/backend/tasks`, and `/opt/server_templates` rather
  than duplicating them, so it never drifts from the running build. Static copies exist only as
  an off-server fallback.
- **Field notes, not a doc mirror.** The `reference/` docs capture the operational knowledge
  that isn't in the product docs; they defer to the server docs on everything else.
- **Version-aware.** See `CLAUDE.md` → *Version awareness* for the bundled-vs-host check.

## Maintenance
- Regenerate the server indexes after a server upgrade: `python3 server-index/generate-index.py`.
- Refresh the static schema copies from the server:
  `cp /opt/backend/workspace-schemas/*.json vswarehouse/schemas/`.
- The repo publishes to `git@github.com:goldenhelix/gh-agent-context.git`.
