# `gautil client` — command-line client for this workspace

`gautil client` is the primary tool for driving VS Warehouse from a shell: manage files &
locations, read/write catalogs, and **run and monitor tasks and workflows**. It authenticates
against the workspace HTTP API using the `GH_*` environment variables that are already set in
this runtime (see the top-level [`CLAUDE.md`](../../CLAUDE.md#the-gh_-environment-variables)),
so in this session you can run commands with **no auth flags** — just `gautil client <command>`.

- Authoritative reference (server, version-matched): `/opt/frontend/docs/tools/gautil-client.md`
- Python equivalent: [`../reference/ghclient-notes.md`](../reference/ghclient-notes.md)
- The run→poll→log→iterate loop: [`./agent-loop.md`](./agent-loop.md)

## Ground rules for scripting it
- **Always pass `--output` explicitly.** `--output=json` gives one document, `--output=jsonl`
  one object per line for `jq -c`; both work on every listing and history command. Defaults
  differ per command and are not worth memorising — naming the format you want costs one flag
  and keeps a script correct across builds. `catalog-info` and `catalog-schema` emit JSON
  whether or not you ask.
- **Failures are loud, so don't muffle them.** An unknown format exits 2; so does an unknown
  flag (`Unknown argument: --limit=2`). **No results is not an error** (`[]` / empty, exit 0).
  Diagnostics go to stderr so stdout stays clean JSON — the corollary is that a blanket
  `2>/dev/null` hides *why* a command produced nothing. Redirect stderr to a file you read on
  failure, not to `/dev/null`.
- **Paths are workspace-relative:** `"<location>/<path>"`, first segment is the file location
  (`Documents`, `Catalogs`, `Automation`, `AppData`, ...). List locations with `file-locations`.
- **This runtime's stdin:** invoke non-interactively (the harness may leave stdin open); the
  commands themselves don't read stdin unless you use a `*-json` variant with a stdin body.
- Exit codes: `0` success (task's own non-zero return code is propagated), `2` usage,
  `3` auth, `4` not found, `5` canceled.

### Gotchas verified on this build (don't get caught by these)
- **A submit-time validation failure exits `0`, not `2`.** `task-run` with a missing required
  parameter prints `Error: Missing parameters: <Name>` to stderr, writes an **empty run-id line**
  to stdout, and **exits 0**. So don't trust the exit code alone to detect a bad submit — verify
  stdout actually contains a non-empty run id: `run_id=$(gautil client task-run … | head -1);
  [ -n "$run_id" ] || { echo "submit rejected"; }`.
- **No per-subcommand `--help`.** `gautil client task-run --help` treats `--help` as the task
  **path** and errors. For the full command surface, run `gautil client` with **no arguments**
  (prints the embedded help) or read `/opt/frontend/docs/tools/gautil-client.md`.
- **`-p` handles list values** as comma-separated: `-p tags=a,b,c`. You only need `task-run-json`
  for values that themselves contain commas, or for machine-generated input.
- **Quote parameter names with spaces.** Real task params often have spaces
  (`String Array Input`) — pass them as `-p "String Array Input=ACGT,TTTT"` (shell-quote the
  whole `name=value`).
- **`file-list [<loc>/<path>] [patterns]` is top-level only** — patterns don't recurse into
  subdirectories. Each returned entry's path is the `url` field (e.g. `/AppData/x.csv`); the
  value you pass back as a task parameter is that path **without the leading slash**
  (`AppData/x.csv`).

## The core loop (copy this)
```bash
# 1) Submit. task-run prints the new run id as the FIRST stdout line (no --output on task-run).
run_id=$(gautil client task-run path/to/thing.task.yaml -p key=value | head -1)

# 2) Wait to completion (or pass --wait / --follow to task-run to block instead of polling).
gautil client task-status "$run_id" --output=json --watch

# 3) On failure read stderr + messages FIRST.
gautil client task-log "$run_id" --output=logfmt --streams=stderr,messages

# 4) Fix the YAML / parameters and rerun. Repeat until green.
```
Workflows are the same shape with `workflow-run` / `workflow-status` / `workflow-monitor`.

> **Task files are discovered under `Automation/Workflows/`** — a path like
> `Automation/Workflows/Tests/hello.task.yaml` runs as `Tests/hello`. Built-in tasks are under
> `System/`. See [`./agent-loop.md`](./agent-loop.md) for path resolution.

## Reading a run's output — the most important skill in the loop
Every fix depends on reading what the run actually printed. A run exposes **three log streams**
plus resource stats; `task-log` interleaves them in chronological order:

| Stream | `text` prefix | Meaning |
|---|---|---|
| `messages` | `[M]` | System/runner messages — step start/stop, `exited with code N`, env dump, the final status. |
| `stdout` | `[O]` | Your step's normal output. |
| `stderr` | `[E]` | Your step's errors — **read this first on failure.** |

Pick the streams and format for the job (`--streams` is comma-separated; **`logfmt` is the
default/best for agents** — one `ts=… stream=… line=… msg="…"` record per line):
```bash
# Triage a failure: the error stream + the runner messages that bracket it.
gautil client task-log "$run_id" --output=logfmt --streams=stderr,messages

# Inspect what the task produced (stdout) alongside step boundaries.
gautil client task-log "$run_id" --output=logfmt --streams=stdout,messages

# Everything, interleaved (default is all streams).
gautil client task-log "$run_id" --output=logfmt

# Quick human view of the last 20 lines across all streams (chronological).
gautil client task-log "$run_id" --color=never --tail=20

# Live-tail a still-running task until it reaches a terminal state.
gautil client task-log "$run_id" --output=logfmt --follow
```
Other `--output` modes: `text` (human, colored), `jsonl`
(`{"t","stream","line","msg"}` per line), `raw` (concatenated stdout+stderr bytes only — no
messages, no framing). Under the hood a run has four files on its status record — `outPath`
(stdout), `errPath` (stderr), `logIndexPath` (the JSONL index that also carries the system
messages and final `returnCode`), and `statsPath` (resource samples) — retrievable via
`task-paths <id>` and downloadable, but `task-log` is what you want 99% of the time.
**Confirm success from the messages/status, not a guess:** terminal `status: completed` **and**
`returnCode: 0`.

## Command index (this server's build)

### Discovery
| Command | Purpose |
|---|---|
| `task-list [--path=<prefix>]` | List configured tasks. `--path` prefix-matches, incl. built-in `System/` tasks. |
| `workflow-list [--path=<prefix>]` | List configured workflows. |
| `file-locations` | List file locations (the valid first path segments). |
| `catalog-list` | List catalogs (by `id`). |

### Run & monitor tasks
| Command | Purpose |
|---|---|
| `task-run <path> [-p name=value]... [opts]` | Run a task. Repeatable `-p`. Opts: `--agent=`, `--cpus=`, `--memory=`, `--runtime-limit=`, `--wait`, `--follow\|-f`, `--notify=`. Prints `taskRunId`. `--wait` blocks & exits with the task's return code. |
| `task-run-json <path> [params.json] [--wait] [--follow]` | Run with a JSON body (stdin or file). Needed only when a value contains commas or is machine-generated — plain list values work with `-p name=a,b,c`. |
| `task-status <id> [--watch]` | Current status; `--watch` polls every 1s until terminal, exits with the task's return code. |
| `task-log <id> [opts]` | Tail/stream the log. `--streams=all\|stdout\|stderr\|messages`, `--tail=N`, `--follow\|-f`, `--output=text\|jsonl\|logfmt\|raw`. |
| `task-stats <id> [--watch]` | Resource usage (CPU/mem/IO) as JSONL. |
| `task-history [--limit] [-q field:op:value]... [--sort=field:dir]` | Past/current runs. `task-history-detail` adds params + messages. |
| `task-paths <id>` | JSON of run/out/err/logIndex/stats paths — pipe into `file-download`. |
| `task-cancel` / `task-delete` / `task-rename <id> <name>` | Control a run. After `task-delete`, `task-status <id>` still exits `0` and returns a record with `status: deleted` (not a not-found error) — that's how you confirm the delete. |

### Run & monitor workflows
| Command | Purpose |
|---|---|
| `workflow-run <path> [opts]` | Run a workflow with overrides. `-p [<stage>.]<name>=<value>` (omit `<stage>.` → first stage), `-s <stage>.<setting>=<value>` (runStep/retryCount/agent/cpus/memory/globEx), `--skip=`/`--include=<stage>[,...]`, `--wait`, `--monitor` (live stage view). |
| `workflow-run-json <path> [input.json]` | Fully-specified run from JSON. |
| `workflow-preview <path> [--trigger]` | Resolve globs / expand per-stage task lists **without running** — sanity-check fan-out first. Note: only expands globs with a **statically-known base**; a base from an upstream stage's `result.env` shows 0 instances (confirm post-run via `workflow-status`/`-monitor`). |
| `workflow-status <id> [--watch]` | Status incl. per-stage state. |
| `workflow-monitor <id> [--interval=SEC]` | Live stage view (ok/running/errored/pending/total + running & failed tasks). |
| `workflow-retry <id>` | Retry an incomplete workflow (originally-skipped stages stay skipped). |
| `workflow-pause` / `workflow-resume` / `workflow-cancel` / `workflow-delete` | Control a run. `workflow-delete` **cascades** — it removes the underlying task-run folders too, so a follow-up `task-delete` on those ids errors with `ENOENT`; that's expected, they're already gone. |
| `workflow-history [--limit] [...]` | Past/current runs; `workflow-history-detail` adds per-stage detail. |

### Files & locations
`file-list [<loc>[/<path>]] [patterns]`, `file-stat`, `file-upload`, `file-download`,
`file-copy`/`file-move`/`file-rename` (`-f` to overwrite), `file-remove [-r]`, `file-mkdir`,
`file-zip`/`file-unzip`, `file-url-upload`/`file-url-check` (server-side fetch),
`file-locations`, `file-create-location`/`file-update-location`/`file-remove-location`.

### Catalogs
`catalog-list`, `catalog-info`, `catalog-schema[-versions]`, `catalog-events`, `catalog-users`,
`catalog-templates`/`catalog-template <id>`, `catalog-export <id> [query]... [--fields=...]`
(also `--output=tsv`), `catalog-upsert <id> field=value...` / `catalog-upsert-json`,
`catalog-import-source`/`catalog-import-tsv`, `catalog-duplicate`/`catalog-backup`/`catalog-restore`,
`catalog-source-version`/`catalog-set-source-version`, record lifecycle
(`catalog-record-publish`/`-approve`/`-archive`), `catalog-delete`, `catalog-reload`,
`catalog-approval-count <id>` / `catalog-set-approval-count <id> <count>` (how many
approvals a record needs), `catalog-rebase-source <id> <loc>/<path> <source_user>
[baseline_user...] [--additive] [--preview]` (re-cut records against a new authority
source version; `--preview` returns counts without modifying anything).

### Storage diagnostics
| Command | Purpose |
|---|---|
| `storage-two-view <local_dir> <location>[/<sub_folder>] [options]` | Compare this machine's view of a directory against the server's view of the same bytes. Runs both directions. |

This is the only command that observes **cross-machine staleness**. A single-host write test
shares one host's caches between its writer and reader, so it can only prove bytes reached the
server — never that a second machine sees them. Reach for it when a task fails on one agent and
passes on another, or when a share has been remounted or rebooted underneath a run.

> For the exact, current flag set on the box you're on, run `gautil client` with no arguments
> (prints the embedded help) or read `/opt/frontend/docs/tools/gautil-client.md`.
