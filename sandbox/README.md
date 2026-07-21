# Sandbox — practice running & fixing tasks end-to-end

A safe place to practice the full agent loop: **make a task discoverable → figure out its
inputs → run it → monitor it → read logs → fix parameters → rerun until green.** These are real,
self-contained tasks (no external data, no special docker image) copied from the shipped server
templates, plus a minimal `hello` task.

| File | What it exercises |
|---|---|
| `hello.task.yaml` | Minimal single `cmd` step — smoke-test the run loop and env vars. |
| `multistep.task.yaml` | Three sequential steps with deterministic stdout/stderr per step — practice reading `task-log` streams. |
| `testAllInputsExample.task.yaml` | Every parameter type (string, list, int, float, boolean, enum, file, directory, optional, disabled). Practice `-p` values — list values are comma-separated (`-p "String Array Input=ACGT,TTTT"`), and file/dir inputs point at real workspace paths (the mounted `Automation/` tree is itself a location, so `Automation/Workflows/Sandbox/…` works with no upload). |

## The exercise
Tasks are only discoverable under the workspace's **`Automation/Workflows/`** tree (see
[`../vswarehouse/reference/agent-loop.md`](../vswarehouse/reference/agent-loop.md) §1). These
files live under `Automation/gh-agent-context/sandbox/`, so **step one is to copy one into
`Automation/Workflows/`** — that copy step is part of the drill.

```bash
# 1) Make it discoverable (pick a scratch subfolder under Workflows you can clean up later)
mkdir -p /home/ghuser/Workspace/Automation/Workflows/Sandbox
cp hello.task.yaml /home/ghuser/Workspace/Automation/Workflows/Sandbox/hello.task.yaml

# 2) Confirm the runner sees it and inspect its inputs
gautil client task-list --path=Sandbox --output=json | jq '.[].path'
gautil client task-list --path=Sandbox/hello --output=json | jq '.[0].parameters'

# 3) Run it, capture the run id, watch to terminal
run_id=$(gautil client task-run Sandbox/hello -p who=agent | head -1)
gautil client task-status "$run_id" --output=json --watch | jq '{status,returnCode}'

# 4) Read the log (logfmt is best for agents)
gautil client task-log "$run_id" --output=logfmt --streams=stdout,messages

# 5) Clean up when done
rm -f /home/ghuser/Workspace/Automation/Workflows/Sandbox/hello.task.yaml
```

Then level up: run `multistep` and read each step's streams; run `testAllInputsExample` and
practice supplying each parameter type (and `task-run-json` for the list-typed ones). Try a
deliberately-bad parameter and watch how the failure surfaces in `--streams=stderr,messages`,
then fix it.

> Housekeeping: keep practice runs in a disposable `Workflows/Sandbox/` folder and delete the
> copied files (and, if you like, the runs via `task-delete <id>`) when finished, so the real
> workspace automation tree stays clean.
