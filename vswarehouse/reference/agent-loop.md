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
`--path=<prefix>` is a prefix match. To learn a task's inputs, read its parameters:
```bash
gautil client task-list --path=<path> --output=json | jq '.[0].parameters'
```

## 1. Where task/workflow files must live (path resolution)
The runner resolves a `<taskConfigPath>` against the workspace's **`Automation/Workflows/`**
tree, with `Automation/Workflows/` stripped and the `.task.yaml` suffix dropped. So
`Automation/Workflows/Tests/hello.task.yaml` is run as **`Tests/hello`**. Files that live
elsewhere (e.g. under `Automation/gh-agent-context/`) are **not discovered** — to run one, copy
it under `Automation/Workflows/` first (newly-added files are picked up immediately, no reload).
Built-in tasks are under the `System/` prefix.

## 2. Submit and wait
`task-run` prints the **new run id as the first stdout line** (plain text — there is no
`--output` on `task-run`). Two idioms:
```bash
# a) capture the id, then poll to a terminal state (exits with the task's returnCode):
run_id=$(gautil client task-run Tests/hello -p who=agent | head -1)
gautil client task-status "$run_id" --output=json --watch

# b) submit + block + stream the log in one call:
gautil client task-run Tests/hello -p who=agent --follow
```
- Repeat `-p name=value` per parameter. **List values are comma-separated** (`-p tags=a,b,c`);
  use `task-run-json` only when a value contains commas or is machine-generated.
- **Quote parameter names with spaces:** `-p "String Array Input=ACGT,TTTT"`.
- `--wait` blocks and exits with the task's `returnCode`; `--follow` implies `--wait` and also
  tails the interleaved log.
- **A missing-required-parameter error exits `0` with an empty run-id line** (validation happens
  client-side before a run is created) — verify `head -1` gave you a non-empty id, don't trust
  the exit code alone.

## 3. On failure, read the log (logfmt is best for agents)
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
wf_id=$(gautil client workflow-run <path> -p [<stage>.]<name>=<value> | head -1)
gautil client workflow-monitor "$wf_id"      # live per-stage view; exits when terminal
gautil client workflow-status  "$wf_id" --output=json --watch
```
- `-p [<stage>.]name=value` sets a stage's task parameter (omit `<stage>.` → first stage);
  `-s <stage>.<setting>=value` overrides `runStep`/`retryCount`/`agent`/`cpus`/`memory`/`globEx`;
  `--skip=`/`--include=<stage>[,...]` toggle optional stages.
- **`workflow-preview <path> [--trigger]`** resolves globs and expands the per-stage task list
  **without running** — preview a fan-out workflow first. **Caveat:** it can only expand a glob
  whose base is statically known; when the base comes from an upstream stage's `result.env` it
  shows **0 instances** (not a bug) — confirm those after running with `workflow-status`/`-monitor`.
- `workflow-retry <id>` reruns the incomplete stages; `workflow-pause`/`-resume`/`-cancel` control a run.

## Exit codes (check them)
`0` success (the task's own non-zero return code is propagated) · `2` usage · `3` auth ·
`4` not found · `5` canceled.
