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
- **Always pass `--output` explicitly.** Four values: `text` (human table, **starts with a
  tab-separated header row**), `tsv` (same columns, no header), `json` (one document), `jsonl`
  (one object per line, for `jq -c`). Every command that emits data takes all four. The default
  is `text` everywhere except `catalog-info` and `catalog-schema`, which default to `json` —
  but name the format you want anyway; it costs one flag and it is the header row on a piped
  `text` listing that produces `jq: parse error: Invalid numeric literal`.
- **stdout is the answer, stderr is everything else.** Progress, banners, confirmations and the
  settled status of a `--wait` all go to stderr, so `stdout` is only the data. A command with
  nothing to return (`task-cancel`, `task-delete`) writes **nothing** to stdout. The corollary
  is that a blanket `2>/dev/null` hides *why* a command produced nothing — redirect stderr to a
  file you read on failure, not to `/dev/null`.
- **Failures are loud, so don't muffle them.** An unknown format, an unknown flag
  (`Unknown argument: --limit=2`) and an unknown command all exit `125`. **No results is not an
  error** (`[]` / empty, exit 0).
- **Paths are workspace-relative:** `"<location>/<path>"`, first segment is the file location
  (`Documents`, `Catalogs`, `Automation`, `AppData`, ...). List locations with
  `file-location-list`.
- **Long options take either spelling:** `--limit=20` and `--limit 20` are the same. A value
  that itself starts with `-` needs the `=` form. `-p`, `-s` and `-q` are repeatable short
  forms that take the next argument.
- **This runtime's stdin:** invoke non-interactively (the harness may leave stdin open); the
  commands themselves don't read stdin unless you use a `*-json` variant with a stdin body.

### Exit codes
The run's own return code passes through `--wait`/`--watch`/`--follow`/`--monitor`, so the
client's own failures use a reserved band above it:

| Code | Meaning |
|---|---|
| `0` | Success. With a wait flag, the run also reached a successful terminal state. Every help request exits 0 too. |
| 1–122, 129–255 | The run's own return code. A failed task's `-1` arrives as `255`; a failed workflow exits `1`. |
| `123` | Request error — unreachable server, or an unusable response. |
| `124` | Request timed out (`GH_TIMEOUT`). |
| `125` | Usage or input error, including an unknown command. |
| `126` | Auth error — credentials missing, rejected, or insufficient. |
| `127` | Not found — no such run id, task path, workflow path, or catalog. |
| `128` | The watched run was canceled. |

A run whose own code lands in 123–128 is ambiguous; read `returnCode` from
`task-status --output=json` when the distinction matters.

### Gotchas verified on this build (don't get caught by these)
- **`-h` is help, not host.** The server url flag is `--host=URL`; you do not need it here,
  the environment already points at this workspace.
- **Per-subcommand help works and exits 0.** `gautil client <command> --help` and
  `gautil client help <command>` both print that command's usage **to stdout**. A bare
  `gautil client` prints the whole command surface. All of them work without credentials.
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
# 1) Submit. stdout is the new run id and nothing else, so capture it directly.
run_id=$(gautil client task-run path/to/thing.task.yaml -p key=value)

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

Pick the streams and format for the job (`--streams` is comma-separated; **`logfmt` is the best
choice for agents** — one `ts=… stream=… line=… msg="…"` record per line):
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
| `file-location-list` | List file locations (the valid first path segments). |
| `catalog-list` | List catalogs (by `id`). |

### Run & monitor tasks
| Command | Purpose |
|---|---|
| `task-run <path> [-p name=value]... [opts]` | Run a task. Repeatable `-p`. Opts: `--agent=`, `--cpus=`, `--memory=`, `--runtime-limit=`, `--wait`, `--follow`, `--notify=`. stdout is the `taskRunId` alone. `--wait` blocks & exits with the task's return code, reporting the settled status on stderr. |
| `task-run-json [request.json] [--wait] [--follow]` | Run from a JSON body (stdin or file) that carries the path **and** the parameters: `{"path": "Tests/example", "parameters": [{"name","value"}...]}`. Needed only when a value contains commas or is machine-generated — plain list values work with `-p name=a,b,c`. |
| `task-status <id> [--watch]` | Current status; `--watch` polls every 1s until terminal, exits with the task's return code. |
| `task-log <id> [opts]` | Tail/stream the log. `--streams=all\|stdout\|stderr\|messages`, `--tail=N`, `--follow`, `--output=text\|jsonl\|logfmt\|raw`. |
| `task-stats <id> [--watch]` | Resource usage (CPU/mem/IO) as JSONL. `--output=jsonl` is the only format it accepts. |
| `task-history [--limit=N] [-q field:op:value]... [--sort=field:dir] [--detail]` | Past/current runs. `--limit` defaults to 50; a full page notes on stderr that it is probably truncated. `--detail` adds params + messages. |
| `task-paths <id>` | JSON of run/out/err/logIndex/stats paths — pipe into `file-download`. |
| `task-cancel` / `task-delete [--purge]` / `task-rename <id> <name>` | Control a run. All three write their confirmation to **stderr**, so stdout is empty. `task-delete` marks the run deleted and removes nothing, so its logs stay readable; `--purge` also removes the run folder. Deleting twice succeeds. Confirm a delete with `task-status <id>`, which still exits `0` and returns `status: deleted`. |

### Run & monitor workflows
| Command | Purpose |
|---|---|
| `workflow-run <path> [opts]` | Run a workflow with overrides. `-p [<stage>.]<name>=<value>` (omit `<stage>.` → first stage), `-s <stage>.<setting>=<value>` (runStep/retryCount/agent/cpus/memory/globEx), `--skip=`/`--include=<stage>[,...]`, `--wait`, `--monitor` (live stage view) with `--interval=SEC`. stdout is the `workflowRunId` alone; the waited status and the monitor view go to stderr. |
| `workflow-run-json [request.json] [--wait] [--monitor]` | Fully-specified run from a JSON body (stdin or file) carrying the path and its stages: `{"path": "Tests/example", "stages": [...]}`. Use `workflow-preview` to see a workflow's stages. |
| `workflow-preview <path> [--trigger]` | Resolve globs / expand per-stage task lists **without running** — sanity-check fan-out first. Note: only expands globs with a **statically-known base**; a base from an upstream stage's `result.env` shows 0 instances (confirm post-run via `workflow-status`/`-monitor`). |
| `workflow-status <id> [--watch]` | Status incl. per-stage state. |
| `workflow-monitor <id> [--interval=SEC]` | Live stage view (ok/running/errored/pending/total + running & failed tasks). `--interval` defaults to 2s. `--output=text\|jsonl` only — it is a stream, so there is no `json`. |
| `workflow-retry <id>` | Retry an incomplete workflow (originally-skipped stages stay skipped). |
| `workflow-pause` / `workflow-resume` / `workflow-cancel` / `workflow-delete [--purge]` | Control a run. `workflow-delete` **cascades** — it marks each of its task runs deleted too, leaving their logs in place; `--purge` also removes each run folder. The workflow is marked deleted even if one of its task runs cannot be, and any per-task failures are reported together at the end. A follow-up `task-delete` on an already-deleted id succeeds rather than erroring. |
| `workflow-history [--limit=N] [...] [--detail]` | Past/current runs; same options and defaults as `task-history`. `--detail` adds per-stage detail. |

### Files & locations
`file-list [<loc>[/<path>]] [patterns]`, `file-stat`, `file-upload`, `file-download`,
`file-copy`/`file-move`/`file-rename` (`-f` to overwrite), `file-remove [-r]`, `file-mkdir`,
`file-zip`/`file-unzip`, `file-url-upload`/`file-url-check` (server-side fetch),
`file-location-list`, `file-location-create`/`file-location-update`/`file-location-remove`.

### Catalogs
`catalog-list`, `catalog-info`, `catalog-schema[-versions]`, `catalog-events`, `catalog-users`,
`catalog-templates`/`catalog-template <id>`, `catalog-export <id> [query]... [--fields=...]`, `catalog-upsert <id> field=value...` / `catalog-upsert-json`,
`catalog-import-source`/`catalog-import-delimited`, `catalog-duplicate`/`catalog-backup`/`catalog-restore`,
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
