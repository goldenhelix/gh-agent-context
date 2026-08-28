# Golden Helix agent context — orientation

You are an AI agent running **on a Golden Helix VS Warehouse server**, inside a workspace, with
tools to drive that server. This repo (`gh-agent-context`) is your grounding: how to use the
CLI/SDK tools, where the docs, schemas, and worked examples live, and the operational gotchas
that aren't obvious from the product docs. **Read this file first**, then open the specific area
you need.

This is the shared agent reference for **all** Golden Helix products. Today it is built out for
**VS Warehouse** (the server you're on) — automating tasks, workflows, catalogs, files, and
workspace management. VarSeq / VS Pipeline / VSClinical scripting are planned; see
[`ROADMAP.md`](./ROADMAP.md).

---

## You are on a live server — verify, don't guess

You have a **working `gautil client`** authenticated as the current user via the environment
(below). Prefer discovering ground truth from the live server over assuming:

```bash
gautil client task-list --output=json | jq -r '.[].path'   # what tasks exist here
gautil client file-location-list --output=json | jq -r '.[].id' # valid file-path prefixes
gautil client catalog-list --output=json | jq -r '.[].id'   # catalogs in this workspace
```

## The `GH_` environment variables

Set in this runtime; `gautil client` and `ghclient` read them automatically, so **no auth
flags/args are needed**. Scripts and one-liners can rely on them being present. The example
values below are illustrative — read the real ones from the environment (`echo "$GH_SERVER_URL"`,
etc.); never hard-code them.

| Variable | Example value | Meaning |
|---|---|---|
| `GH_SERVER` | `example.varseq.com` | Server hostname. |
| `GH_SERVER_URL` | `https://example.varseq.com` | Server base URL. `"$GH_SERVER_URL/version.json"` returns the **host** server version. |
| `GH_WORKSPACE_ID` | `my_workspace` | The workspace you're operating in. |
| `GH_SESSION_KEY` | `SESS_…` | Current user's session key — this is why the client acts **as you**. Treat as a secret; never echo or commit it. |
| `GH_WORKSPACE_ASSEMBLY` | `GRCh_38,Chromosome,Homo sapiens` | Default genome assembly for this workspace (drives `pygautil` coord-sys auto-detection). |

`gautil client` also understands `GH_WORKSPACE_URL` (server URL + workspace combined),
`GH_API_KEY` (service-account key; **session key wins** if both set), and `GH_TIMEOUT` (seconds,
default 3600). The workspace path on the server is `/w/<GH_WORKSPACE_ID>`.

> The `Automation/` workspace folder is mounted into this agent's filesystem, so the workspace's
> own tasks/workflows are directly readable/editable here alongside this repo.

## Tasks vs. workflows

- A **task** is one declarative unit: typed parameters + one or more containerized steps. It is
  the thing you run, and it runs and is **tested individually**.
- A **workflow** is a **DAG of tasks** wired by `depends_on`, threading outputs between stages
  (static params or `result.env` variables via `type: stage`). Some stages **fan out** — one
  task instance per matching input file/directory (glob) or per batch-CSV / parameter-file row.
- Because a workflow's stages are just tasks, **develop and debug each task on its own first**
  (`task-run`), then wire the proven tasks together and run the workflow. When a workflow stage
  fails, reproduce it by running that stage's task standalone with the same parameters.

## The core agentic loop

Running **a task** is this loop — **run → poll → read logs → fix → rerun**:

```bash
run_id=$(gautil client task-run <path> -p name=value | head -1)   # task-run prints the run id (first stdout line)
gautil client task-status "$run_id" --output=json --watch         # poll to terminal; or use --wait/--follow on task-run
gautil client task-log "$run_id" --output=logfmt --streams=stderr,messages   # read this on failure
```

Running **a workflow** is the same loop with the workflow verbs (drive the whole DAG, then drill
into any failed stage's task log):

```bash
wf_id=$(gautil client workflow-run <path> -p [<stage>.]name=value | head -1)
gautil client workflow-monitor "$wf_id"          # live per-stage view; exits when terminal
gautil client workflow-preview <path> --trigger  # expand fan-out WITHOUT running (static bases only; see reference)
```

Full command index (task **and** workflow verbs): [`vswarehouse/reference/gautil-client.md`](./vswarehouse/reference/gautil-client.md).
The narrative playbook: [`vswarehouse/reference/agent-loop.md`](./vswarehouse/reference/agent-loop.md).

## Map — where to look

| To… | Open |
|---|---|
| Drive the server from the shell (run/monitor/files/catalogs) | [`vswarehouse/reference/gautil-client.md`](./vswarehouse/reference/gautil-client.md) |
| Do the same from Python | [`vswarehouse/reference/ghclient-notes.md`](./vswarehouse/reference/ghclient-notes.md) + `/opt/frontend/docs/tools/ghclient.md` |
| Author a task / workflow / plugin | [`vswarehouse/README.md`](./vswarehouse/README.md) → [`reference/task-workflow-authoring.md`](./vswarehouse/reference/task-workflow-authoring.md) |
| Understand the task **execution environment** (`/scratch`, secrets, images, path traps) | [`vswarehouse/reference/environment.md`](./vswarehouse/reference/environment.md) |
| Read/write TSF tracks & catalogs in Python | [`vswarehouse/reference/pygautil-tsf.md`](./vswarehouse/reference/pygautil-tsf.md) + `/opt/frontend/docs/tools/pygautil.md` |
| Copy a **worked example** definition | [`vswarehouse/examples/`](./vswarehouse/examples/) (curated) |
| Find **everything installed on this server** to copy from | [`server-index/`](./server-index/) — built-in tasks + template tasks/workflows |
| Practice running & fixing a task end-to-end | [`sandbox/`](./sandbox/) |
| Validate YAML before submitting | [`vswarehouse/schemas/`](./vswarehouse/schemas/) (static) or `/opt/backend/workspace-schemas/` (version-matched) |
| Call the REST API directly | [`vswarehouse/api/`](./vswarehouse/api/) (OpenAPI specs) |
| Read the full product docs | `/opt/frontend/docs/**/*.md` — **search the `.md`, not the `.html`** |

## Product docs live on the server (search the `.md`)

The full VS Warehouse documentation is bundled on this server at **`/opt/frontend/docs/`**
(~53 Markdown files). This repo intentionally does **not** copy the docs mirror — the server
copy is always version-matched. To find something, grep the Markdown:

```bash
grep -rl "keyword" /opt/frontend/docs --include='*.md'
```

Useful entry points: `docs/getting-started.md`, `docs/api-docs.md`,
`docs/workspaces/automation/` (tasks, workflows, triggers, plugins),
`docs/workspaces/{catalogs,file-management,annotations,applications}.md`,
`docs/workspaces/workspace-management/`, `docs/tools/` (gautil, gautil-client, ghclient,
pygautil), `docs/management/admin/`, `docs/deployment/`.

## Server layout cheat-sheet (this container)

| Path | What |
|---|---|
| `/opt/frontend/docs/**/*.md` | Product documentation (version-matched). |
| `/opt/backend/tasks/` | Built-in `System/` tasks. Indexed: [`server-index/built-in-tasks.md`](./server-index/built-in-tasks.md). |
| `/opt/backend/workspace-schemas/` | `task.json` / `workflow.json` / `application.json` validation schemas. |
| `/opt/server_templates/workspaces/*/Automation/` | Shipped example tasks/workflows/plugins/apps. Indexed: [`server-index/server-templates.md`](./server-index/server-templates.md). |
| `/opt/apiserver/` | `gautil` binary, `pygautil`, `ghclient` (set `PYTHONPATH=/opt/apiserver` for the Python libs). |
| `/opt/frontend/dist/version.json` | The version **this container** was bundled from. |

## Version awareness

This repo is **version-agnostic** — it ships no pinned version and is pulled into every server
release, so **never assume a version; read it from the running system:**

```bash
cat /opt/frontend/dist/version.json          # the version THIS container was bundled from
curl -s "$GH_SERVER_URL/version.json"        # the version the HOST server reports
```

- If the container-bundled version and the host-server version diverge meaningfully, trust the
  **live server** for API/schema/behavior and re-derive from it.
- The static copies in this repo (schemas, API specs, server indexes) are only a fallback for
  when you're off-server; the version-matched files on disk (`/opt/backend/workspace-schemas/`,
  `/opt/frontend/docs/`, …) always win. Regenerate the static copies against the current server
  after an upgrade — see the maintenance notes in [`README.md`](./README.md).

## How to help well
1. **Verify against the live server first** (list tasks/locations/catalogs, read the real
   schema) before writing or asserting anything.
2. **Ground on the worked examples and the field notes** before authoring from scratch —
   prefer adapting a shipped example (`server-index/` → copy → edit) over greenfield YAML.
3. **Run the loop to green.** Submit, watch, read stderr+messages on failure, fix the exact
   parameter/path, rerun. Don't declare success without a terminal `complete`/return code 0.
4. **Keep secrets safe.** `GH_SESSION_KEY` and workspace secrets are credentials — never echo
   them into logs, files, or task descriptions.
