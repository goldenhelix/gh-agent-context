# The task execution environment (agent field notes)

Every task step runs **inside a container**. By default a step runs in the **default server
image** (`registry.goldenhelix.com/gh/server:<this-server-version>`); add `docker: {image: ...}`
to point either step type at another image. What `type` actually controls is the **wrapper**:
`type: cmd` wraps your `args` in `bash -c 'set -e; ...'`, `type: docker` hands your `args` straight
to the image's own entrypoint with no shell. Either way the workspace is bind-mounted in and the
container is torn down when the step finishes. These are the things that bite agents and aren't
obvious from the product docs. Authoritative CLI/SDK references live on the server at
`/opt/frontend/docs/tools/*.md`; this file is the hard-won operational layer on top.

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

The runner turns a cmd step into `bash -c 'set -e;<your args joined by ;>'` — so `set -e` is
already on, and multiple `args` entries become one script joined by `;` (keep it to a single `|-`
block). A bash step's args are **not** interpolated by the server: `$VAR` is expanded by the shell
in-container. Any other `command:` gets its args `${VAR}`-substituted by the runner instead.

`type: cmd` picks the **image** independently of the shell wrapper: add `docker: {image: …}` to a
`cmd` step to run your bash script inside another image — this is what every shipped template does
(`germline_vspipeline` and `System/download_annotation_source` both run
`${VSPIPELINE_DOCKER_IMAGE}` from a `cmd` step). Omit `docker:` and you get the default server
image.

## Python & libraries in the default server image
`python3` is the bundled CPython 3.10.15 at `/opt/python/bin`, first on `PATH`. `pygautil` is a
cpython-310 extension, so it imports only under that interpreter — don't build a venv or install
another python and expect `import pygautil` to work. Debian's own `/usr/bin/python3` (3.11) is
also in the image: a login shell (`bash -lc`) on a server image without `/opt/agent-context` resets `PATH` and
picks it up, along with losing `gautil`. Call `/opt/python/bin/python3` explicitly if you must use
a login shell there.

Pre-installed and load-bearing: `requests`, `jinja2`, and the Golden Helix libs **`pygautil`** and
**`ghclient`** at `/opt/apiserver/` (already on `PYTHONPATH` in this image). Do not assume anything
else, including `pandas`, `pyyaml`, or `jsonschema` — check with `python3 -c 'import x'` in a probe
step before building a task around a library.

Key binaries: `curl`, `wget`, `git`, `gautil`, `jq`, `yq`, `rg`, `rsync`, `samtools`/`bcftools`
(htslib), `node`, the `docker` CLI. Run `command -v <tool>` before assuming a binary is missing.

## `PYTHONPATH=/opt/apiserver` for pygautil / ghclient
`pygautil`, `ghclient`, and `gautil` live at `/opt/apiserver` **in the server image only** (and
images derived from it, e.g. the VSAgent image). `PYTHONPATH=/opt/apiserver` is already set there,
so a `cmd` step running the default image needs nothing.

To run a script that needs `pygautil`/`ghclient` inside another image, don't rely on `PYTHONPATH`:
that directory doesn't exist in a third-party or VarSeq/VSPipeline image, and nothing mounts it in.
Either split the work into two steps (one in the other image, one back in the server image), or
call the tool from a `cmd` step that overrides `docker: image:` — this keeps the bash wrapper while
running another image:
```yaml
steps:
  - name: align
    description: …
    type: cmd
    docker:
      image: ${VSPIPELINE_DOCKER_IMAGE}
    args:
      - |-
        set -euo pipefail
        cd /scratch
        /opt/vspipeline/vspipeline -c batch file=…
```
Reserve `type: docker` for handing an image an argv list for its own entrypoint: it gets no shell
and no `set -e`, and its `args` are interpolated by the runner, not by bash.

## Injected environment variables & workspace paths
The run log's `Running with env:` block shows the parameter/workspace/GH_*/AGENT_* set.
`WORKSPACE_DIR`, `SCRATCH_DIR`, and any step-level `env:` entries are set in the container but
deliberately not printed there (so app/task passwords don't get logged) — run `env | sort` in a
probe step to see everything.

The load-bearing ones:

| Var | Example (in a `data_curation` task) | Use |
|---|---|---|
| `WORKSPACE_DIR` | `/w/data_curation` | **Workspace mount root.** Build paths to sibling scripts/data: `${WORKSPACE_DIR}/Automation/Workflows/.../script.py`. |
| `TASK_DIR` | `/w/<ws>/Automation/Workflows/<path-to-task>` | The task file's own directory — reach sibling scripts with `"$TASK_DIR/script.py"`. For a `System/` built-in it is the server's baked task folder instead, `/opt/backend/tasks/<subpath>` — not under `/w`. |
| `TASK_NAME` | `probe` | The task's config name. |
| `SCRATCH_DIR` | `/scratch` | The same directory the container has bind-mounted at `/scratch` (see below). |
| `GH_SERVER` / `GH_SERVER_URL` / `GH_WORKSPACE_ID` / `GH_WORKSPACE_ASSEMBLY` | — | Same `GH_*` set as the agent runtime (see [`../../CLAUDE.md`](../../CLAUDE.md#the-gh_-environment-variables)); `gautil`/`ghclient` read them. `GH_SESSION_KEY` is injected only if the task sets `auto_generate_session_for_account` (below). |
| `AGENT_CPU_CORES` / `AGENT_MEMORY_GB` | `1` / `0.1` | This run's resource grants — pass to tools that take a thread/mem arg. |
| `AGENT_RUNTIME_LIMIT` | `30` | Set only when the task declares `agent_requirements.runtime_limit_seconds` (or the run overrides it) — read it as `${AGENT_RUNTIME_LIMIT:-}` under `set -u`. |

For the full injected set and the step/parameter YAML contract, see the server's own
`/opt/frontend/docs/workspaces/automation/workflow-details.md` (environment variables table — note
it also lists `GH_WORKSPACE_URL` and `GH_API_KEY`, which the task runner does not actually inject)
and `/opt/backend/workspace-schemas/task.json`.

**Custom workspace variables** (configured per workspace in Settings) inject exactly the same way.
Every workspace is seeded with `RESOURCES_PATH` (e.g. `Documents/resources`) and `REFERENCE_PATH`
(the assembly's reference fasta); admins add more on the workspace Settings page. Reference them as
`${VAR}` in bash — run `env | sort` in a probe step to see what this workspace actually defines.

Parameter `value:` defaults are injected verbatim: no variable expansion of any kind. Write a plain
workspace-relative path (`Automation/Workflows/Tests/tasks`) for a `file`/`directory` parameter
(the runner prefixes the mount for you), and build anything variable in the step from
`${WORKSPACE_DIR}`.

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
- `/scratch` is one directory per **run** (`<agent scratch_storage|/var/tmp>/<runner id>`, removed
  when the run ends), so all steps of a task share it — fine for handing intermediates between
  steps, and gone by the next run.
- **Exception — `result.env`:** the file a step writes to export computed variables downstream
  must land in the step's **run output directory** (its CWD *before* you `cd /scratch`). Capture
  `run_dir="$PWD"` first, then write `"$run_dir/result.env"`. See
  [`task-workflow-authoring.md`](./task-workflow-authoring.md#passing-computed-outputs-between-stages-resultenv).

## Workspace secrets are auto-injected env vars
Secrets uploaded at the **workspace** level are exported into every task container's env by name
automatically. You do **not** need a `type: secret` parameter or an `env:` entry — just read
`$SECRET_NAME` in your script.

The run log's `Running with env:` listing masks secret-flagged vars (`SECRET_NAME=****`), but
**nothing scrubs your script's own output**. Never `echo` a secret, avoid `set -x` in a step that
touches one, and keep tokens out of command lines that get logged. (In this workspace's run log you
can see e.g. `OMIM_API_KEY=****`, `SLACK_WEBHOOK_*=****`, `TRELLO_TOKEN=****` in that listing only.)

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

For a step that calls an LLM, set `auto_generate_ai_key_for_account:` (same value set as above) at
the task top level. When workspace AI is enabled the runner mints a scoped, revocable
OpenAI-compatible key and injects `GH_AI_BASE_URL`, `GH_AI_API_KEY`, `GH_AI_DEFAULT_MODEL`,
`GH_AI_MODELS`; it is revoked when the run ends. Treat `GH_AI_API_KEY` like `GH_SESSION_KEY`.

## Choosing a `docker` step image
- **For Golden Helix images, reference the workspace image variables in a step's `docker: image:`
  field** — not a literal tag: `${DEFAULT_DOCKER_IMAGE}` (the server image, from the server
  process env), `${VSPIPELINE_DOCKER_IMAGE}` and `${VARSEQ_DOCKER_IMAGE}` (seeded per workspace and
  bumped by `ghadmin workspace-update-images` on upgrade). `${VSAGENT_DOCKER_IMAGE}` and other
  `*_DOCKER_IMAGE` vars exist only when an application or plugin checkout pinned them. These
  resolve server-side for the `image:` field only — they are **not** environment variables, so your
  script cannot read them. This is what the shipped templates do (`germline_vspipeline`, the
  VarSeq/VSCode applications, …).
- **Pin a literal tag only for third-party / bioinformatics images** from Docker Hub, quay.io,
  etc. (e.g. `biocontainers/bwa:0.7.17`), where a fixed version is what you want for reproducibility.
- **The runner never pulls.** If the image is missing the step fails with `Image <name> not found,
  make sure it is available on the local docker host!` — except on a remote (ssh) agent, where the
  runner transfers it from the server host if the server has it. Either way the image has to be
  pulled on the server first. A tag you add to a task YAML is not registered until an image scan
  runs (a scan fires on plugin changes and inside `System/application_checkout` /
  `System/plugin_checkout` / `System/workflow_checkout`, not on saving a task). For a new
  third-party tag, ask a workspace admin to scan and pull from the admin Docker Images page (or
  `ghadmin workspace-images-scan <ws>` then `ghadmin workspace-images-pull <ws> --missing`). Note:
  the checkout tasks' own log line claiming a missing image "will be pulled when a task next needs
  it" is wrong — the runner never pulls.

## Path gotchas (still worth knowing)
- **`type: directory` / `type: file` pickers are for workspace locations** (the ones
  `gautil client file-location-list` lists) — they inject as `/w/<workspace>/<location>/…` absolute
  paths. Don't hand them arbitrary host paths.
- Only `type: file` and `type: directory` parameters are rewritten on injection (they get the
  `/w/<workspace>/` mount prefix). Every other type, `type: string` included, arrives exactly as
  typed — a relative path stays relative, and it is on your script to join it to `${WORKSPACE_DIR}`
  or a workspace variable. Prefer building data paths in the step over passing path-like string
  parameters.
