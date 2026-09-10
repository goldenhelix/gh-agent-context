# Automation examples

Curated task/workflow/plugin definitions to copy and adapt. Most are real shipped Golden Helix
server templates; the fan-out set was authored here and **verified end-to-end on a live server**.
For everything installed on **this** server, see [`../../server-index/`](../../server-index/).

Field semantics (stage/step/parameter keys, fan-out rules) are covered in
[`../reference/task-workflow-authoring.md`](../reference/task-workflow-authoring.md) and the
server's bundled docs at `/docs`; flag grammar is covered by `gautil client <command> --help`.
The tables below call out only what each file uniquely shows plus its non-obvious gotchas.

## Tasks (`tasks/`)
| File | Demonstrates |
|---|---|
| `generate_files.task.yaml` | **Fan-out producer** (verified). A `cmd` step that writes N files and emits the output directory **workspace-relative** to `result.env` for a downstream glob — encodes the `${output_dir#/w/${GH_WORKSPACE_ID}/}` gotcha. |
| `process_file.task.yaml` | **Fan-out consumer** (verified). Processes one file per instance; shows a `type: file` param fed by `${0}` and a `type: string` param fed by `${basename}`, plus a plain `type: directory` output param with a default. |
| `germline_vspipeline.task.yaml` | A real VS Pipeline analysis task: directory/string/file params, `agent_requirements`, `auto_generate_session_for_account: "{workspaceBot}"`, a `cmd` step running in a custom image (`docker: image: ${VSPIPELINE_DOCKER_IMAGE}`). **Best-practice image reference:** `image: ${VSPIPELINE_DOCKER_IMAGE}` — a workspace-defined image var that tracks the server upgrade cycle (use these for Golden Helix images; pin literal tags only for third-party images). |
| `create_catalog.task.yaml` (+ `catalog_task.py`) | The real "Create Workspace Catalogs" task: many **grouped** (`group:`) typed params incl. multi-select `enum` `list: true`, `auto_generate_session_for_account: "{user}"`, and a `cmd` step that calls its bundled helper script via `python3 "$TASK_DIR/catalog_task.py"` — a complete example of a task shipping its own script. |
| `multistep.task.yaml` | Multiple sequential steps. (Uses `command: bash`; the idiomatic `cmd` shape **omits** `command:` — see [`../reference/task-workflow-authoring.md`](../reference/task-workflow-authoring.md).) |
| `create_data_set.task.yaml`, `analyze_data_set.task.yaml` | The pair used by `example_analysis.workflow.yaml`. |

## Workflows (`workflows/`)
| File | Demonstrates |
|---|---|
| `glob_fanout.workflow.yaml` | **Fan-out over files a prior stage produced (verified 4/4).** Stage 1 generates files → Stage 2 `glob_parameter` runs one instance per match. Encodes the two gotchas: use `parameter_expression` (not `stage_parameter`) in the glob `path`, and a workspace-relative base. Pairs with `generate_files` + `process_file`. |
| `example_analysis.workflow.yaml` | Multi-stage with data passing: `depends_on` + `type: stage`/`stage_parameter` threads stage 1's output into stage 2. |
| `batch_file.workflow.yaml` | Fan-out over a **batch CSV** — one instance per row (header columns → task params). Minimal stub; see the authoring reference for the full `batch_file_parameter` shape. |
| `param_file.workflow.yaml` | Load one set of `name=value` parameters from a file (not fan-out: one instance). Minimal stub. |

## Plugins (`plugins/`)
| File | Demonstrates |
|---|---|
| `pgx-catalog-builder.plugin.yaml` | A real plugin manifest: `plugin:` block with a `command:` and no image (so it runs on the default server image), env-driven catalog-template bootstrap (`UPSERT_CATALOGS_SYSTEM_TEMPLATES`), `auto_generate_session_for_account: "{workspaceAdminBot}"`. |
| `whoami.plugin.yaml` | A minimal plugin — smallest complete manifest to start from, and the one that pins its own image (`traefik/whoami:latest`). |

## Study a full production workflow
The examples here are minimal on purpose. For a complete, well-structured, real workflow — proper
repo layout (`README.md`, entry workflow + `tasks/` + `scripts/`), rich Markdown task descriptions,
`${TASK_DIR}/../scripts/` script paths, `stage_parameter_expression` sharing one input across
stages, `result.env` dynamic hand-off, and `read_only`/`persist_key`/`path` parameter hygiene —
read the shipped **Cohort Allele Frequency** workflow (`github.com/goldenhelix/cohort-analysis`;
on a server, `Automation/Workflows/Cohort Allele Frequency/`). Its patterns are distilled in
[`../reference/task-workflow-authoring.md`](../reference/task-workflow-authoring.md) (see
*Packaging a workflow as a repository*).

> Provenance: the analysis/utility/plugin files are copied from the shipped `server_templates`;
> the `glob_fanout` set (`generate_files` + `process_file` + `glob_fanout.workflow.yaml`) was
> authored and run to green here. For more real examples, grep
> [`../../server-index/server-templates.md`](../../server-index/server-templates.md).
