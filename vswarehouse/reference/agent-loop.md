# Playbook: run → poll → read logs → fix → rerun

The core loop for driving VS Warehouse: submit work, wait, read logs on failure, fix the
definition/parameters, rerun until green. This is the **agent-specific procedure**; for the full
command surface and every flag, the authoritative reference is the server's own doc —
**read `/opt/frontend/docs/tools/gautil-client.md`** (and `gautil.md` / `ghclient.md` /
`pygautil.md` alongside it). A condensed command index is in
[`../reference/gautil-client.md`](../reference/gautil-client.md).

Auth is already configured from the `GH_*` environment (see [`../../CLAUDE.md`](../../CLAUDE.md));
run `gautil client <command>` with **no auth flags**.

## 0. Discover before you assume
```bash
gautil client task-list --output=json      | jq -r '.[].path'   # tasks that exist here
gautil client workflow-list --output=json  | jq -r '.[].path'   # workflows
gautil client task-list --path=System --output=json | jq -r '.[].path'   # built-in System/ tasks
```
`--path=<prefix>` matches a folder prefix (`Tests` or `Tests/hello`), not a partial name. To learn
a task's inputs, read its parameters:
```bash
gautil client task-list --path=<path> --output=json | jq '.[0].parameters'
```

## 1. Where task/workflow files must live (path resolution)
The runner resolves a `<taskConfigPath>` against the workspace's **`Automation/Workflows/`**
tree, with `Automation/Workflows/` stripped and the `.task.yaml` suffix dropped. So
`Automation/Workflows/Tests/hello.task.yaml` is run as **`Tests/hello`**. Files that live
elsewhere (e.g. under `Automation/gh-agent-context/`) are **not discovered** — to run one, copy
it under `Automation/Workflows/` first (newly-added files are picked up immediately, no reload).
Built-in tasks are under the `System/` prefix. Never create your own files under
`Automation/Workflows/System/`: that prefix is reserved for the built-ins and workspace files
there are ignored.

## 2. Submit and wait
`task-run` prints the **new run id as the first stdout line** (plain text — there is no
`--output` on `task-run`). See `gautil client task-run --help` for the full flag list. Two idioms:
```bash
# a) capture the id, then poll to a terminal state (exits with the task's returnCode):
run_id=$(gautil client task-run Tests/hello -p who=agent)
gautil client task-status "$run_id" --output=jsonl --watch   # one JSON object per poll; last line is the settled status

# b) submit + block + stream the log in one call:
gautil client task-run Tests/hello -p who=agent --follow
```
- **`--output=json` is refused with `--watch`** (exit `125`): a single JSON document can't stream
  one-per-poll. Use `--output=jsonl` (or `text`/`tsv`) with `--watch`; keep `--output=json` for a
  one-shot snapshot.
- Repeat `-p name=value` per parameter. List values are comma-joined strings in both `-p` and
  `task-run-json` (`-p tags=a,b,c`) — there is no other list encoding, the task receives the
  string as-is. Use `task-run-json` when the request is generated or read from a file.
- **Quote parameter names with spaces:** `-p "String Array Input=ACGT,TTTT"`.
- `--wait` blocks and exits with the task's `returnCode`; `--follow` implies `--wait` and also
  tails the interleaved log. `--wait` reports the settled status once, on stderr — stdout stays
  the run id alone, so `$(...)` captures exactly what you want.
- **A rejected submit exits non-zero with nothing on stdout**, so `if gautil client task-run …;
  then` is a sound test. A missing required parameter or an unknown `-p` name is rejected by the
  server: exit `123` with `HTTP 400: Missing parameters: <Name>` (or `HTTP 400: Invalid parameter
  <name>`) on stderr. An unknown task path exits `127` (`HTTP 404: Task not found at path <path>`).
  Exit `125` is reserved for the client's own argument errors (unknown flag, bad `--output`).

## 3. On failure, read the log (logfmt is best for agents)
See `gautil client task-log --help` for the full flag list.
```bash
gautil client task-log "$run_id" --output=logfmt --streams=stderr,messages   # triage failures
gautil client task-log "$run_id" --output=logfmt --streams=stdout,messages   # normal output
gautil client task-log "$run_id" --color=never --tail=20                     # quick human view
```
Streams: `[M]` message · `[O]` stdout · `[E]` stderr. `logfmt` emits one record per line with
`ts`/`stream`/`line`/`msg`. A run also has resource stats (`task-stats <id>`) and file paths
(`task-paths <id>`, pipe into `file-download`).

## 4. Fix and rerun
Read the actual error, fix the **exact** thing (a wrong parameter value, a path that resolved to
somewhere unexpected, a missing docker image, a bad import), and rerun step 2. Common causes are
in [`../reference/environment.md`](../reference/environment.md) (path-resolution traps,
`/scratch`, `PYTHONPATH`, un-pulled images). **Don't declare success without a terminal
`completed` status and `returnCode` 0.**

## Workflows — same shape
```bash
wf_id=$(gautil client workflow-run <path> -p [<stage>.]<name>=<value>)   # stdout is exactly the run id
gautil client workflow-monitor "$wf_id"      # live per-stage view; exits when terminal
gautil client workflow-status  "$wf_id" --output=jsonl --watch
```
See `gautil client workflow-run --help` (and `workflow-status`/`-preview`/`-retry`/`-pause`/
`-resume`/`-cancel --help`) for the full flag list. Gotchas:
- `-p [<stage>.]name=value` sets a stage's task parameter. Omit `<stage>.` when only one stage
  declares the name (it's resolved to that stage); when several do, the first stage is used if it
  declares the name, otherwise the client demands the prefix (exit `125`). Unknown stages,
  parameters and settings are rejected before anything is submitted.
- `-s <stage>.<setting>=value` overrides `runStep`/`retryCount`/`agent`/`cpus`/`memory`/`globEx`;
  `--skip=`/`--include=<stage>[,...]` toggle optional stages.
- **`workflow-preview <path> [--trigger]`** resolves globs and expands the per-stage task list
  **without running** — preview a fan-out workflow first. **Caveat:** it can only expand a glob
  whose base is statically known; when the base comes from an upstream stage's `result.env` it
  shows **0 instances** (not a bug) — confirm those after running with `workflow-status`/`-monitor`.
- `workflow-retry <id>` reruns the incomplete stages; `workflow-pause`/`-resume`/`-cancel` control a run.
- `--output=json` is refused with `--watch` here too, same as `task-status`.

## Exit codes (check them)
`0` success (with a wait flag, the run also completed) · `1`-`122`/`129`-`255` the run's own
return code (a failed task's `-1` arrives as `255`; a failed workflow exits `1`) · `123` request
error (server unreachable, or the request was rejected, e.g. HTTP 400) · `124` timeout
(`GH_TIMEOUT`, or `--watch --timeout` expired) · `125` usage error (bad client arguments) ·
`126` auth · `127` not found (run id, task path, or workflow path) · `128` the watched run was
canceled or deleted. A run whose own return code lands in `123`-`128` is indistinguishable from a
client failure by exit code alone; read `returnCode` from `--output=json` when it matters.
