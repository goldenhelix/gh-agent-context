# The task execution environment (agent field notes)

Every task step runs **inside a container**. A `type: cmd` step runs in the **default server
image** (`registry.goldenhelix.com/gh/server:<this-server-version>`, chosen by the runner); a
`type: docker` step runs in the **named image** you specify. Either way the workspace is bind-
mounted in, your `args` script runs, and the container is torn down. These are the things that
bite agents and aren't obvious from the product docs. Authoritative CLI/SDK references live on
the server at `/opt/frontend/docs/tools/*.md`; this file is the hard-won operational layer on top.

## `type: cmd` steps: omit `command:`, just give the `args` body
The idiomatic shape (the vast majority of real tasks) is **no `command:` key** — a `type: cmd`
step with a single-element `args:` heredoc that runs as a **bash** script:
```yaml
steps:
  - name: do_it
    description: What this does.
    type: cmd
    args:
      - |-
        set -euo pipefail
        cd /scratch
        python3 "$TASK_DIR/script.py" --out "${output_dir}"
```
`command:` is optional (the step schema only requires `name`, `description`, `type`); setting
`command: bash` also works but is redundant. `$0` inside such a step is `bash` (verified).

## Python & libraries in the default server image
- Use **`python3`** — never `python3.8`.
- Pre-installed: `requests`, `urllib3`, `lark`, `ruamel.yaml`, `regex`, `jinja2`, plus the
  Golden Helix libs **`pygautil`** and **`ghclient`** at `/opt/apiserver/`.
- **Not** installed (verify before relying on them): `pandas`, `lxml`, `openpyxl`,
  `BeautifulSoup`, `jsonschema`, `pyyaml`. Check imports before writing a task around them.
- Key binaries: `curl`, `wget`, `git`, `gautil`.

## `PYTHONPATH=/opt/apiserver` for pygautil / ghclient
In a **`docker` step**, reference the image and (if needed) set `PYTHONPATH`:
```yaml
steps:
  - name: align
    type: docker
    docker:
      image: ${VSPIPELINE_DOCKER_IMAGE}    # workspace-defined image var — see below
      workspace_mount: /workspace          # optional: remap the workspace mount for this image
      # shared_memory_size: 512m           # optional
    env:
      PYTHONPATH: /opt/apiserver
    args:
      - |-
        cd /scratch
        python3 "$TASK_DIR/script.py"
```
In a **`cmd` step** (default server image) `pygautil`/`ghclient` already resolve; setting
`PYTHONPATH=/opt/apiserver` is harmless and portable.

## Injected environment variables & workspace paths
The runner injects a rich environment (seen in the run log's "Running with env:" block). The
load-bearing ones:

| Var | Example (in a `data_curation` task) | Use |
|---|---|---|
| `WORKSPACE_DIR` | `/w/data_curation` | **Workspace mount root.** Build paths to sibling scripts/data: `${WORKSPACE_DIR}/Automation/Workflows/.../script.py`. |
| `TASK_DIR` | `/w/<ws>/Automation/Workflows/<path-to-task>` | The task file's own directory — reach sibling scripts with `"$TASK_DIR/script.py"`. |
| `TASK_NAME` | `probe` | The task's config name. |
| `GH_SERVER` / `GH_SERVER_URL` / `GH_WORKSPACE_ID` / `GH_WORKSPACE_ASSEMBLY` | — | Same `GH_*` set as the agent runtime (see [`../../CLAUDE.md`](../../CLAUDE.md#the-gh_-environment-variables)); `gautil`/`ghclient` read them. `GH_SESSION_KEY` is injected only if the task sets `auto_generate_session_for_account` (below). |
| `AGENT_CPU_CORES` / `AGENT_MEMORY_GB` / `AGENT_RUNTIME_LIMIT` | `1` / `0.1` / `30` | This run's resource grants — pass to tools that take a thread/mem arg. |

**Custom workspace variables** (configured per workspace in Settings) inject exactly the same
way — e.g. this workspace exposes `CURATION_PATH`, `SHIPPED_TRACKS_PUBLIC`, `RESOURCES_PATH`.
Reference them as `${VAR}` in bash. In a **parameter `path:` default** the same variables appear
in **single-brace** form, e.g. `value: "{WORKSPACE_DIR}/Automation/Workflows/Tests/tasks"`.

## Workspace paths mount at `/w/<workspace>/<location>`
Workspace file locations are bind-mounted at **`/w/<GH_WORKSPACE_ID>/<location>`** (e.g.
`/w/data_curation/Automation`, `/w/data_curation/Documents`, `/w/data_curation/AppData`). This is
also what a `type: file` / `type: directory` **parameter injects**: you pass a workspace-relative
value (`Automation/Workflows/foo`, `Documents/in.csv`) and the step receives the **absolute**
`/w/<workspace>/Automation/Workflows/foo` — use it directly, no mount prefix to prepend. (A
`docker` step can remap the mount with `workspace_mount:`.)

## Always `cd /scratch` first
- `/scratch` is the container's **local disk** (bind-mounted per run) — the working directory for
  all intermediate files (downloads, extraction, temp files).
- **Start each step's script with `cd /scratch`.** Target `/scratch` explicitly for temp I/O
  (`tempfile.TemporaryDirectory(dir="/scratch")`). Only **outputs that must persist** get written
  to a workspace location (a `/w/<workspace>/<location>/…` path).
- **Exception — `result.env`:** the file a step writes to export computed variables downstream
  must land in the step's **run output directory** (its CWD *before* you `cd /scratch`). Capture
  `run_dir="$PWD"` first, then write `"$run_dir/result.env"`. See
  [`task-workflow-authoring.md`](./task-workflow-authoring.md#passing-computed-outputs-between-stages-resultenv).

## Workspace secrets are auto-injected env vars
Secrets uploaded at the **workspace** level are exported into every task container's env by name
automatically. You do **not** need a `type: secret` parameter or an `env:` entry — just read
`$SECRET_NAME` in your script. Runtime logs auto-redact any secret-flagged var (`SECRET_NAME=****`),
so logs are safe by default. (In this workspace's run log you can see e.g. `OMIM_API_KEY=****`,
`SLACK_WEBHOOK_*=****`, `TRELLO_TOKEN=****` — all redacted.)

Idiom worth copying — **degrade gracefully when a secret is unset** so scripts stay runnable in
dev/CI:
```python
webhook = os.environ.get("SLACK_WEBHOOK_ANNOTATIONS")   # unset -> notify() is a no-op
if webhook:
    post_to_slack(webhook, msg)
```
- Use **workspace secrets** for pipeline-wide credentials shared across runs.
- Use a **`type: secret` parameter** only for a one-off credential the operator supplies per run.

## Session identity inside a task
By default no `GH_SESSION_KEY` is injected. If a step must call back into the workspace API as a
real identity, set `auto_generate_session_for_account:` at the **task** top level — the runner
injects a `GH_SESSION_KEY` for that account. Values: a service-account username, or the tokens
`{user}` (the initiating user), `{workspaceBot}`, `{workspaceAdminBot}`. Pick by **permission**:
routine work uses `{workspaceBot}`; operations needing `catalog:manage` (e.g. creating a catalog)
need `{workspaceAdminBot}`. In-container, authenticate a tool with
`Cookie: GH_SessKey=$GH_SESSION_KEY` (the cookie name comes from
`$GH_SERVER_URL/auth/api/authenticationMethod`). Never echo the key.

## Choosing a `docker` step image
- **For Golden Helix images, use the workspace-defined image variables — not a literal tag.**
  The workspace injects `${DEFAULT_DOCKER_IMAGE}` (the server image), `${VSPIPELINE_DOCKER_IMAGE}`,
  `${VARSEQ_DOCKER_IMAGE}`, and `${VSAGENT_DOCKER_IMAGE}`, and these are **bumped automatically on
  the server upgrade cycle** — referencing them keeps every task on the matching version with no
  hand-editing. This is what the shipped templates do (`germline_vspipeline`, the VarSeq/VSCode
  applications, …).
- **Pin a literal tag only for third-party / bioinformatics images** from Docker Hub, quay.io,
  etc. (e.g. `biocontainers/bwa:0.7.17`), where a fixed version is what you want for reproducibility.
- **Images are not auto-pulled.** A `docker` step fails if its image isn't already on the agent —
  ensure it's pre-pulled (Golden Helix image vars resolve to already-present images; third-party
  images must be pulled, e.g. via `System/plugin_checkout` / `System/application_checkout`).

## Path gotchas (still worth knowing)
- **`type: directory` / `type: file` pickers are for workspace locations** (the ones
  `gautil client file-locations` lists) — they inject as `/w/<workspace>/<location>/…` absolute
  paths. Don't hand them arbitrary host paths.
- A **`type: string` parameter whose value *looks like* a relative path** may be resolved by the
  server to an absolute path before injection; if your script then prepends another base, you get
  a broken doubled path. For data paths, prefer building the full path **in the step** from
  `${WORKSPACE_DIR}` / workspace variables over passing a path-like string parameter.
