# Roadmap

`gh-agent-context` is the shared agent reference for **all** Golden Helix products. It is being
built out first for the surface an agent uses **on a VS Warehouse server** (done ✅), then
outward to VarSeq automation and the scripting/customization surfaces.

## Done — VS Warehouse agentic tooling ✅
The first goal: get an agent fluent with the server's CLI/SDK tools and able to look up inputs,
outputs, examples, and schemas for **tasks, workflows, files, catalogs, and workspace
management**.
- `gautil client` command reference + the run→poll→log loop — `vswarehouse/reference/`
- `ghclient` / `pygautil` field notes — `vswarehouse/reference/`
- Task/workflow authoring + execution-environment gotchas — `vswarehouse/reference/`
- Searchable indexes of on-server built-in tasks + template examples — `server-index/`
- Hands-on sandbox for running & fixing a task end-to-end — `sandbox/`

## Planned — VarSeq & VS Pipeline
- **VS Pipeline** (`vspipeline`) CLI command reference for headless VarSeq automation (the
  `${VSPIPELINE_DOCKER_IMAGE}` container used by the germline/cancer example tasks). Needs the
  Pipeline Runner add-on; not available on macOS.
- VarSeq algorithm/annotation reference relevant to building analysis tasks on the server.

## Planned — scripting & customization
The embedded-JS and Python scripting surfaces that customize VarSeq/VSClinical output. Keep these
distinct — they use different APIs; don't mix them:
- **VSClinical evaluation scripts** — drive an ACMG/AMP evaluation (`CustomScript.run`).
  *Started:* anatomy, API pointers and the headless `vspipeline` path are in
  [`vsclinical/evaluation-scripts.md`](./vsclinical/evaluation-scripts.md).
- **VSClinical evaluation reports** — custom report rendering inside an evaluation.
- **Table reports** — read project data → Word/text (e.g. PGx, STR).
- **Report scripts** (project/report JS API) and legacy **VS Reports** (`form.*`, deprecated).
- API **type definitions** (TypeScript / apirson) to ground script authoring.

These have rich material in the internal GoldenMind SDK (`varseq/`, `types/`, `examples/`,
`how-tos/`, `genomebrowse/`) not yet brought into this on-server context. Pull them in when an
agent workflow on the server needs them (e.g. a task that runs an evaluation script or renders a
custom report), scrubbing customer-specific content on the way in.

## Maintenance conventions
- Keep pointing at the server's version-matched files (`/opt/frontend/docs`,
  `/opt/backend/workspace-schemas`, `/opt/backend/tasks`, `/opt/server_templates`) rather than
  copying them; regenerate `server-index/` after each server upgrade.
- New reference docs are **field notes** that complement the product docs, not a second copy.
