# Authoring tasks & workflows (agent field notes)

Distilled, load-bearing conventions for writing `*.task.yaml` / `*.workflow.yaml`. The
**authoritative field references** are the server's own docs — read them for the full option
list — and the **validation schemas** are the contract:

- Field docs (server): `/opt/frontend/docs/workspaces/automation/task-details.md`,
  `.../workflow-details.md`, `.../triggers-and-schedules.md`, `.../plugins.md`
- Schemas (version-matched, server-local): `/opt/backend/workspace-schemas/{task,workflow,application}.json`
- Static schema copies (this repo): [`../schemas/`](../schemas/)
- Worked examples: [`../examples/`](../examples/) and the
  on-server template index in [`../../server-index/server-templates.md`](../../server-index/server-templates.md)

**Always validate against the schema before submitting.** The server also validates at submit
time, so a quick path is to just submit and read the error — but catching it locally is faster.
Note the agent runtime ships `ruamel.yaml` but **not** `jsonschema` or `pyyaml`, so the obvious
one-liner may not run; reliable options: diff your YAML against the closest
[`../examples/`](../examples/) file, or load the schema JSON with `json` + `ruamel.yaml` and
check each object against its `required` / `additionalProperties` by hand.

## Task YAML — required top-level fields
`name`, `parameters`, `steps`, `agent_requirements`.

```yaml
name: My Task                     # display name (user-facing); need not match the filename
description: |-
  # Markdown renders here
  Task descriptions support **multi-line Markdown** (headings, lists) and it renders in the UI —
  use it for real operator guidance. For a task that's only meant to run inside a workflow, say so:

  ## Important
  This task is run by the "My Workflow" workflow — don't run it directly.

auto_generate_session_for_account: "{user}"   # optional; see environment.md

agent_requirements:
  cpu_cores: 2
  memory_gb: 4
  # optional: scheduler_cpu_cost, runtime_limit_seconds

alternative_agent_requirements:               # optional, run-time-selectable profiles
  Large:
    cpu_cores: 8
    memory_gb: 16
    description: For large inputs

parameters:
  - name: output_dir            # referenced in args as ${output_dir}
    label: Output Directory
    type: directory             # string|float|integer|boolean|enum|file|directory|secret|catalog
    help: Where results are written
    supports_location_mode: read_write   # read_only for inputs
  - name: run_date
    label: Run Date
    type: string
    optional: true
    value: ""                   # empty string = filled at run time

steps:
  - name: Do the thing
    description: What this step does.
    type: cmd                   # cmd = default server image; docker = a named image
    # no `command:` — a cmd step's single args heredoc runs as bash (command is optional)
    args:
      - |-
        cd /scratch
        python3 "$TASK_DIR/script.py" --out "${output_dir}"
```

### Parameter notes
- `${param_name}` substitutes the value into `command` / `args`.
- `type: enum` needs a `choices:` list; add `list: true` for multi-select. `list: true` also
  works on `string`/`file` for multi-value inputs.
- `type: file` / `type: directory` render a picker over **workspace locations**; add
  `pattern_match: ['*.vcf.gz']` to filter the file picker. The **value you pass is
  workspace-relative** (`<location>/path`, e.g. `Automation/Workflows/…` — the mounted
  `Automation/` tree is itself a location), and it **arrives in the step as an absolute
  `/w/<workspace>/<location>/…` path** you use directly (no mount prefix). See the path-resolution
  gotchas in [`environment.md`](./environment.md). A `value:` default for these is a string path.
- `supports_location_mode:` accepts **`read_write`**, **`read_only`**, or **`no_append`**.
  **Best practice: mark inputs `read_only`** (the picker then can't grant write access it doesn't
  need); use `read_write` only on a parameter the task actually writes to.
- **Give every parameter a `label` and a `help`.** Both render in the run dialog; `help` is where
  you explain accepted values/format (the shipped tasks put filter-expression syntax there).
- `path:` on a `file`/`directory` parameter sets the **picker's default location**
  (e.g. `path: AppData/Common Data/UserAnnotations/cohorts`) — point operators at the right folder.
- `create: true` on a `file` parameter lets the operator **name a not-yet-existing** output file.
- `persist_key: 'ns.key'` remembers the entered value as a workspace default for next time; use a
  dotted namespace (`cohorts.input_directory`) to avoid collisions.
- `group: 'Advanced Options'` collapses less-common parameters into a section.
- `type: catalog` — a parameter that selects a workspace catalog by id (see
  [`ghclient-notes.md`](./ghclient-notes.md) / `gautil client catalog-list`).
- `type: secret` — per-run credential, prompted at run time, never logged. For pipeline-wide
  secrets prefer **workspace secrets** (auto-injected env vars — see
  [`environment.md`](./environment.md)).
- `editable: false` disables an input; `optional: true` allows it empty; `value:` sets a default.
- `$TASK_DIR` inside a step resolves to the **task file's own directory** — use it to reach
  helper scripts by a path relative to the task, which is far more robust than an absolute one.
  With the recommended layout (tasks in `tasks/`, scripts in `scripts/`), that's
  **`"${TASK_DIR}/../scripts/foo.py"`** — this is how the shipped workflows call their scripts.

## Workflow YAML — required fields
`name`, `stages`.

```yaml
name: My Workflow
description: One or two sentences.

stages:
  - name: Pull
    task_path: ./tasks/pull.task.yaml     # relative to the workflow file
    run_step: always                      # always | optional_default_run | optional_default_skip
    retry_count: 2
    task_parameters:
      - name: output_dir
        label: Raw Data Output            # REQUIRED on every task_parameters item (name+type+label)
        type: directory
        value: some_location/raw

  - name: Curate
    task_path: ./tasks/curate.task.yaml
    depends_on: [ Pull ]                  # stage NAMES, not task names
    task_parameters:
      - name: input_dir
        label: Input Directory
        type: stage                       # thread a value from an upstream stage
        stage: Pull
        stage_parameter: output_dir       # ...an upstream *parameter*, or a result.env var (see below)
      - name: output_dir
        label: Staging Output
        type: directory
        value: some_location/staging
```
> Every `task_parameters` item requires **`name`, `type`, and `label`** — the schema rejects an
> item missing `label` even though the task's own parameter has one. (Don't copy the terser
> task-level parameter shape here.)

### Stage notes
- `depends_on` is a list of upstream **stage names**.
- `type: stage` parameters pull a value from an upstream stage downstream — this is how data
  flows between stages. `stage_parameter: <name>` names either the upstream stage's own
  parameter **or a `result.env` variable it emitted** (see below);
  `stage_parameter_expression` computes one from those + the upstream inputs.
- Fan-out patterns (one task instance per input): **glob** (`glob_parameter`), **batch CSV**
  (`batch_file_parameter`, one row per instance), **parameter file** (`parameter_file`). See the
  **Fan-out** section below.
- `run_step: optional_default_skip` exposes a stage in the UI but leaves it unchecked by
  default (e.g. a force-re-run step). `retry_count: N` retries a failed stage up to N times
  (put it on flaky network stages).
- **A stage only exposes a task parameter to `workflow-run -p` (and the run dialog) if the stage
  restates it in `task_parameters`.** Omit it and the stage silently runs with the task's
  **defaults** — a real footgun when the default is dangerous (e.g. `dry_run: false`). This is
  why real workflows restate parameters the task already declares.
- **Parameter-source precedence** (later overrides earlier): `batch_file_parameter` →
  `parameter_file` → `glob_parameter` → `task_parameters`.

### Workflow-level agent profiles
Alongside per-task `alternative_agent_requirements`, a **workflow** can declare selectable
resource profiles at its root and per stage:
```yaml
requirements_configurations:                 # workflow root: selectable profiles
  - { name: Standard, description: Default }
  - { name: Large, description: More memory for big inputs }
selected_requirements_configuration: Standard
stages:
  - name: Curate
    agent_requirements: { cpu_cores: 4, memory_gb: 16, runtime_limit_seconds: 7200 }  # per-stage override
    ...
```

### Passing *computed* outputs between stages: `result.env`
A `type: stage` parameter can only pull a **static** upstream parameter value. To pass something
a step **computed at runtime** (a generated file path, a record count, a version string), the
step writes a **`result.env`** file and the downstream stage reads those variables by name via
`stage_parameter`:

```yaml
# upstream task step:
steps:
  - name: generate
    type: cmd
    args:
      - |-
        run_dir="$PWD"          # capture the run OUTPUT dir BEFORE any cd
        cd /scratch             # do work on local disk
        # ... produce data, persist it to a workspace location (absolute $output_dir) ...
        # emit computed outputs for downstream stages:
        echo "data_file=${output_dir}/numbers.csv" >> "$run_dir/result.env"
        echo "row_count=20"                          >> "$run_dir/result.env"
```
```yaml
# downstream stage consumes them:
  - name: Transform
    task_path: ./tasks/transform.task.yaml
    depends_on: [ Generate ]
    task_parameters:
      - name: input_file
        label: Input File
        type: stage
        stage: Generate
        stage_parameter: data_file      # <- the result.env KEY, not a declared parameter
      - name: expected_rows
        label: Expected Rows
        type: stage
        stage: Generate
        stage_parameter: row_count
```
Rules that bite (verified on this server):
- **Format:** one `KEY=value` per line; blank lines and `#` comments ignored.
- **Location matters.** `result.env` must land in the step's **run output directory** — its
  default CWD. Since every step should `cd /scratch` first (see
  [`environment.md`](./environment.md)), capture `run_dir="$PWD"` *before* the `cd` and write
  `"$run_dir/result.env"`. Writing it to `/scratch` means downstream stages never see it.
- Between **steps of one task**, `result.env` variables auto-merge into the next step's env
  (reference them as `$VAR`). Between **stages of a workflow**, they're pulled via `type: stage`.
- Persist the actual **data** to a workspace **location** (not `/scratch`, which is per-container
  ephemeral). File/directory parameters inject as absolute `/w/<workspace>/<location>/...` paths
  that survive across steps, stages, and container images — so an absolute path emitted to
  `result.env` works downstream when consumed by a **`type: stage` file/directory parameter**.
- **Caveat — a `glob_parameter.path` base must be workspace-RELATIVE, not absolute** (see the
  Fan-out section). When you'll feed a directory to a downstream glob, emit the relative form:
  `echo "gen_dir=${output_dir#/w/${GH_WORKSPACE_ID}/}" >> "$run_dir/result.env"`.

#### `stage_parameter` vs `stage_parameter_expression` — and sharing one input across stages
A `type: stage` parameter resolves against the upstream stage's **input parameters *and* its
`result.env` variables**, two ways:
- `stage_parameter: name` — a direct lookup by key.
- `stage_parameter_expression: '${name}'` — interpolation (can combine several,
  e.g. `'${dir}/${file}'`).

A common real pattern: an early stage takes a shared input (e.g. a `parameter_file` the operator
selects once), and **every later stage re-references it** by expression so it's chosen only once:
```yaml
stages:
  - name: VCF Input
    task_path: tasks/cohort_manifest.task.yaml
    task_parameters:
      - { name: parameter_file, label: Parameter File, type: file,
          path: 'AppData/Common Data/UserAnnotations/cohorts',   # picker default location
          persist_key: 'cohorts.parameter_file' }
  - name: Merge Results
    task_path: tasks/cohort_update.task.yaml
    depends_on: [ 'Process VCF Manifests' ]
    task_parameters:
      - name: parameter_file          # re-use the file the operator picked in "VCF Input"
        label: Parameter File
        type: stage
        stage: VCF Input
        stage_parameter_expression: '${parameter_file}'    # its INPUT param
      - name: manifest_parameter_file
        label: Manifest parameter file
        type: stage
        stage: VCF Input
        stage_parameter_expression: '${output_manifest_list}'   # a result.env var it emitted
```
(Adapted from the shipped **Cohort Allele Frequency** workflow — see *Packaging* below.)

## Fan-out (one task instance per input)
A stage with `glob_parameter` or `batch_file_parameter` runs the task **once per match/row**.
The canonical case: an upstream stage produces a set of files, a downstream stage fans out over
them.

### `glob_parameter` (verified end-to-end on this server)
```yaml
  - name: Process
    task_path: ./tasks/process.task.yaml
    depends_on: [ Generate ]
    glob_parameter:
      path:                              # base directory to match under
        type: stage
        stage: Generate
        parameter_expression: '${gen_dir}'   # <- see the TWO gotchas below
      glob_ex: '*.txt'                   # capture groups: each * is a group
      continue_if_no_match: true         # skip instead of failing when nothing matches
      output_parameters:                 # map captures -> the task's parameters
        - { task_parameter_name: input_file,  expression: '${0}' }        # full matched path
        - { task_parameter_name: sample_name, expression: '${basename}' } # filename w/o extension
```
**Capture expressions** (dollar-brace): `${0}` full matched path, `${1}`,`${2}`,… successive `*`
groups, plus `${directory}` (base), `${file_directory}`, `${file_name}`, `${basename}`,
`${file_extension}`. Wildcards: `*` one level, `**` recurse, `***` greedy.

**Two gotchas that cost real debugging time — both verified:**
1. **Field name is `parameter` / `parameter_expression`, NOT `stage_parameter`.** Inside
   `task_parameters` you use `stage_parameter` / `stage_parameter_expression`; inside a
   `glob_parameter.path` (`type: stage`) it's **`parameter` / `parameter_expression`**. Using
   `stage_parameter` here makes the stage **silently expand to 0 instances with no error** — the
   worst failure mode. (An older shipped example got this wrong.)
2. **The glob base must be workspace-RELATIVE.** Directory params / `result.env` emit absolute
   `/w/<workspace>/…` paths, but `glob_parameter.path` wants a relative path — an absolute one
   fails with `Glob file does not yet exist: 'w/...'`. Emit the relative form upstream:
   `echo "gen_dir=${output_dir#/w/${GH_WORKSPACE_ID}/}" >> "$run_dir/result.env"`.

**`workflow-preview --trigger` is blind to runtime-derived glob bases.** When the base comes from
an upstream stage's `result.env`, preview shows the stage with **0 instances** (indistinguishable
from a broken glob); it only pre-expands statically-known bases (a fixed `value:` or a direct
`parameter:` of a declared param). For runtime bases, confirm the fan-out **after running** with
`workflow-status` / `workflow-monitor` (e.g. `Process [OK] 4/4`).

### `batch_file_parameter` / `parameter_file`
- `batch_file_parameter`: one instance per **row** of a CSV/TSV; the **header column names map to
  task parameter names** (`.csv` = comma, else tab).
- `parameter_file`: loads `key=value` pairs from a file for a **single** stage run.

## Idempotency & version-gated skip (the production pipeline pattern)
The real curation pipelines on this server don't lean on `result.env` for data-passing; they use
a durable, restartable convention worth copying for scheduled work:
- A first **`version-check`** stage compares the upstream source version to the last-shipped one
  and writes a `version_check.json` (`status: up_to_date | update_available`) to a **deterministic
  staging path** — it **always exits 0**; the status lives in the file, not the exit code.
- Each later stage reads that file and **early-exits when `up_to_date`**, so re-runs are cheap and
  safe.
- Stages hand off via **JSON sidecar files at fixed staging paths** (e.g. `pull_manifest.json`)
  rather than threading everything through `result.env`.
- `retry_count` guards flaky network stages. `result.env` / `type: stage` is still correct for
  small computed handoffs — just not the whole data path.

## Steps: `cmd` vs `docker`
Both run in a container (see [`environment.md`](./environment.md)).
- `type: cmd` runs in the **default server image** (has `python3`, `pygautil`, `ghclient`,
  `gautil`, `curl`, `git`). Simplest; use it for glue, downloads, file wrangling, curation
  scripts, and API calls. **Omit `command:`** — the `args` heredoc runs as bash.
- `type: docker` runs in a **named image** (`docker.image`), with optional `workspace_mount:` and
  an `env:` block. Use it to pin a specific toolchain (e.g. VS Pipeline). For **Golden Helix
  images use the workspace image variable** (`${VSPIPELINE_DOCKER_IMAGE}`, `${VARSEQ_DOCKER_IMAGE}`,
  `${DEFAULT_DOCKER_IMAGE}`) so the version tracks the server upgrade cycle; **pin a literal tag
  only for third-party images** (Docker Hub / quay). **Images are not auto-pulled.** See
  [`environment.md`](./environment.md#choosing-a-docker-step-image).
- Steps run **sequentially**, each in its own container; a step's `result.env` variables merge
  into the next step's environment (see below).

## Packaging a workflow as a repository (layout & conventions)
Shipped, production-grade workflows follow a consistent layout — copy it. Exemplar: the
**Cohort Allele Frequency** workflow (`github.com/goldenhelix/cohort-analysis`, checked out on
this server at `Automation/Workflows/Cohort Allele Frequency/`; install one with the
`System/workflow_checkout` task).

```
My Workflow/
├── README.md                 # operator guide: Usage (numbered steps), Process, Output
├── LICENSE
├── .gitignore                # e.g. scripts/__pycache__
├── my.workflow.yaml          # the entry-point WORKFLOW (what operators run)
├── define_thing.task.yaml    # optional first-run/setup task, at top level (operators run it)
├── tasks/                    # per-stage helper tasks — invoked BY the workflow
│   ├── stage_a.task.yaml
│   └── stage_b.task.yaml
└── scripts/                  # helper scripts the tasks call
    ├── foo.py
    └── util.py
```

**Why this shape**
- **Entry points at the top, internals in `tasks/`.** The workflow (and any explicit first-run
  task like *Define Cohort*) sit at the top level — those are what an operator should launch.
  The per-stage tasks live in `tasks/`. They're still discoverable, so each one's **description
  states it's driven by the workflow and shouldn't be run directly** (a Markdown "## Important"
  block) — that's how you keep operators on the supported path.
- **Scripts in `scripts/`, reached via `${TASK_DIR}/../scripts/…`** — tasks in `tasks/` call
  `python3 "${TASK_DIR}/../scripts/foo.py"`, so the workflow relocates/renames cleanly and works
  regardless of the workspace it's checked out into.
- **Naming.** File names describe the role (`cohort_manifest.task.yaml`); the display `name:` is
  the user-facing label ("Cohort Manifest Generator") and need not match the filename. Give the
  workflow the verb-first name operators will look for ("Build Cohort Annotation Track").
- **Docs live in three places, each for its audience:** the top-level `README.md` for the full
  operator guide (usage steps, process, output, assembly notes); the workflow/stage `description`
  for a one-liner; each task `description` for rich Markdown "how to use / don't run directly".
  Every parameter carries a `label` + `help`.
- Persist the data the workflow produces to a durable workspace location (e.g.
  `AppData/Common Data/UserAnnotations/...`), and point pickers there with `path:` +
  `persist_key:` so re-runs are one click.
