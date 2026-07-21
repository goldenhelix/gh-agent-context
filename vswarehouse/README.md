# VS Warehouse — agent reference

Everything an agent needs to **author, run, and iterate on** VS Warehouse tasks, workflows, and
plugins, plus the CLI/SDK/API references and the operational field notes. Orientation for the
whole server is in the top-level [`../CLAUDE.md`](../CLAUDE.md); this is the VS Warehouse subtree.

## The model in one paragraph
A **task** is a declarative unit: typed parameters + one or more steps, each a shell script run
either on the agent host (`type: cmd`) or inside a container image (`type: docker`). A
**workflow** chains tasks into **stages** with `depends_on` dependencies, threading outputs
between stages via `type: stage` parameters, and can fan out over many inputs (glob / batch-CSV /
parameter-file). A **plugin** packages a long-lived capability (e.g. a catalog builder) with its
own container and bootstrap. You run and monitor all of them with **`gautil client`** (or the
`ghclient` Python SDK), driving the same run→poll→log→iterate loop.

## What's here
| Folder | What |
|---|---|
| [`reference/`](reference/) | **Agent field notes** — all the how-to knowledge and gotchas. Start here: [`reference/README.md`](reference/README.md). Contains the [`agent-loop.md`](reference/agent-loop.md) run→poll→log→fix→rerun procedure, the [`gautil-client.md`](reference/gautil-client.md) command index, task/workflow authoring, the execution environment, and `ghclient`/`pygautil` notes. |
| [`examples/`](examples/) | Curated, runnable `*.task.yaml` / `*.workflow.yaml` / `*.plugin.yaml` to copy from. See [`examples/README.md`](examples/README.md). For everything installed on **this** server, see [`../server-index/`](../server-index/). |
| [`schemas/`](schemas/) | JSON Schemas that validate task/workflow/application YAML. |
| [`api/`](api/) | OpenAPI / REST specs for the workspace + admin APIs. |

## Source of truth: server-local beats static committed
> **You are almost certainly running on a VS Warehouse server** (this repo is deployed on the
> box). The version-matched files are right there on disk — prefer them. The static copies here
> are the off-server fallback.

| Artifact | Prefer (on server) | Fallback (this repo) |
|---|---|---|
| Product docs | `/opt/frontend/docs/**/*.md` | — (not mirrored; search the server) |
| Validation schemas | `/opt/backend/workspace-schemas/{task,workflow,application}.json` | [`schemas/`](schemas/) |
| REST OpenAPI | live `/swagger/` (or `/auth/api/me/openApiUrls`) | [`api/`](api/) |
| Built-in tasks | `/opt/backend/tasks/` | [`../server-index/built-in-tasks.md`](../server-index/built-in-tasks.md) |
| Template examples | `/opt/server_templates/` | [`../server-index/server-templates.md`](../server-index/server-templates.md) |

Rule of thumb: **server-local (version-matched) beats static committed.** The static copies
exist so you're never blocked without server access — not to override the truth on the box
you're on. When in doubt, re-derive from the live server. This repo is version-agnostic and
pulled into every release; the static copies are refreshed from whatever server they're
regenerated against — check the running version with `cat /opt/frontend/dist/version.json` (see
[`../CLAUDE.md`](../CLAUDE.md#version-awareness)).
