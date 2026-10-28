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
| `WORKSPACE_DIR` | `/home/ghuser/Workspace` | The mounted workspace root; your persistent area is `$WORKSPACE_DIR/Documents/$USERNAME`. |
| `USERNAME` | `jdoe` | Your login on this server. |
| `GH_AI_BASE_URL`, `GH_AI_API_KEY`, `GH_AI_DEFAULT_MODEL`, `GH_AI_MODELS` | — | Set only when workspace AI is enabled: an OpenAI-compatible endpoint and a per-launch key scoped to you, revoked when this agent closes. `GH_AI_MODELS` is comma-separated. Secret; never echo. |

`gautil client` also understands `GH_WORKSPACE_URL` (server URL + workspace combined),
`GH_API_KEY` (service-account key), and `GH_TIMEOUT` (seconds; `gautil client` defaults to
3600, `ghclient` to 300 — see `gautil client --help` → Environment Variables for authoritative
semantics). Precedence differs by tool: `gautil client` uses `GH_API_KEY` when both are set;
`ghclient` uses `GH_SESSION_KEY`. In this container only `GH_SESSION_KEY` is set; don't add
`GH_API_KEY` to `.vsagent.env` unless you want `gautil` to stop acting as you.

> The whole workspace is mounted at `$WORKSPACE_DIR` (`/home/ghuser/Workspace`;
> `/w/$GH_WORKSPACE_ID` is a symlink to it). Each file location is a subfolder: `Documents/`,
> `Catalogs/`, `Automation/` (tasks/workflows/plugins/apps), so a workspace path
> `Documents/x.vcf` is `$WORKSPACE_DIR/Documents/x.vcf` on disk. `Automation/` is read-only
> unless you are a workspace admin; use `file-upload` or ask an admin to change tasks in place.
> Your persistent area is `Documents/$USERNAME/`.

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
run_id=$(gautil client task-run <path> -p name=value)   # stdout is exactly the run id
gautil client task-status "$run_id" --watch --output=jsonl   # one status object per poll; exits with the task's return code
gautil client task-log "$run_id" --output=logfmt --streams=stderr,messages   # read this on failure
```

Running **a workflow** is the same loop with the workflow verbs (drive the whole DAG, then drill
into any failed stage's task log):

```bash
wf_id=$(gautil client workflow-run <path> -p [<stage>.]name=value)   # stdout is exactly the run id
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
| Query an annotation source (track/TSF) through the server, incl. one you just uploaded | [`vswarehouse/reference/annotation-lookup.md`](./vswarehouse/reference/annotation-lookup.md) |
| Copy a **worked example** definition | [`vswarehouse/examples/`](./vswarehouse/examples/) (curated) |
| Find **everything installed on this server** to copy from | [`server-index/`](./server-index/) — built-in tasks + template tasks/workflows |
| Practice running & fixing a task end-to-end | [`sandbox/`](./sandbox/) |
| Validate YAML before submitting | [`vswarehouse/schemas/`](./vswarehouse/schemas/) (static) or `/opt/backend/workspace-schemas/` (version-matched) |
| Call the REST API directly | [`vswarehouse/api/`](./vswarehouse/api/) (OpenAPI specs) |
| Read the full product docs | `/opt/frontend/docs/**/*.md` — **search the `.md`, not the `.html`** |

## Product docs live on the server (search the `.md`)

The full VS Warehouse documentation is bundled on this server at **`/opt/frontend/docs/`**
(`find /opt/frontend/docs -name '*.md'` for the live list). This repo intentionally does **not**
copy the docs mirror — the server copy is always version-matched. To find something, grep the
Markdown:

```bash
grep -rl "keyword" /opt/frontend/docs --include='*.md'
```

Useful entry points: `docs/getting-started.md`, `docs/api-docs.md`,
`docs/workspaces/automation/` (tasks, workflows, triggers, plugins),
`docs/workspaces/{catalogs,file-management,interpretation-configuration,applications,ai-assistance}.md`,
`docs/workspaces/workspace-management/`, `docs/tools/` (gautil, gautil-client, ghclient,
pygautil), `docs/management/admin/`, `docs/deployment/`.

## Server layout cheat-sheet (this container)

| Path | What |
|---|---|
| `/opt/frontend/docs/**/*.md` | Product documentation (version-matched). |
| `/opt/backend/tasks/` | Built-in `System/` tasks. Indexed: [`server-index/built-in-tasks.md`](./server-index/built-in-tasks.md). |
| `/opt/backend/workspace-schemas/` | `task.json` / `workflow.json` / `application.json` / `plugin.json` validation schemas. |
| `/opt/server_templates/workspaces/*/Automation/` | Shipped example tasks/workflows/plugins/apps. Indexed: [`server-index/server-templates.md`](./server-index/server-templates.md). |
| `/opt/apiserver/` | `gautil` binary, `pygautil`, `ghclient` (already on `PATH` and `PYTHONPATH`; use plain `python3`, which is the 3.10 build `pygautil` is compiled for — do not call `/usr/bin/python3`). |
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
   parameter/path, rerun. Don't declare success without a terminal `completed` status / return
   code 0 (terminal states: completed, failed, canceled, deleted, skipped).
4. **Keep secrets safe.** `GH_SESSION_KEY`, `GH_AI_API_KEY`, and workspace secrets are
   credentials — never echo them into logs, files, or task descriptions.
