# VSClinical evaluation scripts (agent field notes)

An **evaluation script** (a `CustomScript`) is a JavaScript module that runs against one open
VSClinical evaluation — typically to import findings from a vendor file (Archer, TSO500, …),
prune variants, or add interpretations. In the GUI it appears in the evaluation's script menu;
headlessly it runs through `vspipeline` (below). The run behavior here was verified on
**VarSeq 3.1.0 EA5** (build 23304, the server's `${VSPIPELINE_DOCKER_IMAGE}`); the API source
was read from a VarSeq build of 2026-04-21. Re-check the `@types` and the server implementation
for the build you are on.

Not to be confused with *evaluation reports* (`report_cancer.js`), *project reports*
(`project_report.js`) or *workflow scripts* (the `run_workflow_script` driver below) — different
entry points, though they share the same `cancer`/`acmg`/`core` API.

## Anatomy

A script is a folder under `ReportTemplates/` whose name is the menu label, holding
`script_cancer.js` (AMP / cancer evaluations) and/or `script_acmg.js` (ACMG / germline):

```js
// @ts-check
/** @type {import('../@types/custom_script').CustomScript} */
export default {
    description: 'Shown under the folder name',
    inputType: 'SingleFile',          // or 'MultipleFiles'; omit for no file prompt
    fileFilter: 'My files (*.tsv)',
    icon: 'import',                   // file | import | export | gear
    inputFiles: [],                   // sibling files read into `inputs`
    binaryFileTypes: [],              // extensions read as binary instead of utf8
    async run({ selected, inputs, api: { cancer, core, table }, args }) {
        const evaluationId = parseInt(args[0]);   // args[0] is always the evaluation ID
        const [fileText] = selected;              // CONTENTS of the picked file(s), not paths
        // ...
    }
};
```

`run` is executed by `Data/runner.js run_script …` in a Node process that talks to VarSeq over
a websocket (`VSAPI_WS_PORT`), so it can't be run standalone — use the GUI or `vspipeline`.

## Where the ground truth lives

In any VarSeq install (`find / -path '*Data/ReportTemplates/@types' 2>/dev/null`):

| Path (under `Data/`) | What |
|---|---|
| `ReportTemplates/@types/custom_script.ts` | The `CustomScript` / `run()` contract above. |
| `ReportTemplates/@types/vsc_api.d.ts` | Every `cancer.*` / `acmg.*` / `core.*` call and return type. Inputs show only as `InferMutationInput<'cancer.addCnv'>` … |
| `interpretations_embedded_server.js` | … so grep here for `mutation('addCnv'` / `query('getCnv'` to read the real input schema (zod `objectType({...})` with defaults) and the resolver logic. |
| `ReportTemplates/*/script_*.js` | Shipped scripts to copy: *Import Archer Fusions and Deletions*, *Import TSO500 All Splice Variants*, *Import TSO 500 Combined TSV*, *Import Project Variants, CNVs, and SVs*, *Remove Benign Variants*, … |
| `runner.js` | How `selected` / `inputs` / `args` are assembled. |

Calls used most when importing into an AMP evaluation (all take `evaluationId`):

| Call | Notes |
|---|---|
| `cancer.addVariant({ variant })` | `variant` is HGVS (`NM_000245.4:c.3028+1G>T`). Optional `origin`, `reportAs`, `callState`, `readAltCount`, `readDepthCount`, `vaf`. |
| `cancer.addCnv({ cnv })` | `cnv` is a query string, e.g. `7:116771849-116771989 DEL` (1-based, inclusive). See the transcript-form gotcha below. Optional `copyNumber`, `ratio`, `origin`. |
| `cancer.addRearrangement({ sv })` / `parseRearrangement` | Fusions, e.g. `GENE1::GENE2 <bkpt5> <bkpt3>` or `GENE1-GENE2`. |
| `cancer.preferredTranscriptForGene({ geneName })` | Returns the evaluation's transcript incl. `chr`, `strand`, `exonCount`, `exonStarts`/`exonStops` (0-based, ascending genomic). |
| `cancer.getEvaluationBiomarkers()` | `[{ id, mutation: { name, description, annotationScope }, possibleMutations }]` — check what an import actually became. |

## Running one headlessly (vspipeline)

There is no direct "run this CustomScript" CLI command; instead a vs-batch file runs a
**workflow script** that calls `cancer.runCustomScript` (pattern taken from the VarSeq
regression test TC-613.2, which does the same for ACMG):

```
project_create path="project" template="<template with a VSClinical view>"
import files="<sample.vcf>"
download_required_sources
task_wait
set_current_workflow amp Workflow5 fix=True
foreach_sample "run_workflow_script driver.js {name}" affected_only=False
wait_for_scripts_to_complete
project_close
```

```js
// driver.js — workflow scripts get cancer/acmg as globals and top-level await
const { evaluationId } = await cancer.createEvaluation({ tumorType: 'Non-Small Cell Lung Cancer' });
await cancer.runCustomScript({
    scriptName: '/abs/path/My Script/script_cancer.js',   // or just 'My Script' (ReportTemplates folder)
    args: [String(evaluationId)],
    selectedFiles: ['/abs/path/input.tsv'],                 // paths here; the script receives contents
});
console.log(JSON.stringify(await cancer.getEvaluationBiomarkers({ evaluationId })));
export { };
```

A complete, verified VSW task is in
[`examples/headless-evaluation-script/`](./examples/headless-evaluation-script/): copy the folder
to `Automation/Workflows/VSClinical Evaluation Scripts/` and
`gautil client task-run "VSClinical Evaluation Scripts/run_evaluation_script"` (~40 s; override
`script_file` / `selected_file` to test your own script).

### Gotchas
- **The project needs a VSClinical workflow view.** `set_current_workflow <acmg|amp|cancerkb> <viewId>`
  attaches the workflow to an existing view; the view ID comes from the template
  (`Comprehensive Cancer Template GRCh38` → `Workflow5`; grep the template for
  `VSWorkflowViewOptions` → `userId`). Templates without one (e.g. the shipped Cancer Example)
  can't host an evaluation.
- **`foreach_sample` defaults to `affected_only=True`** and silently skips samples with no
  affected status — pass `affected_only=False` for tumor/unannotated samples.
- **One failed batch command cancels the rest** (`"Canceled"`, code -100). `get_view_list`
  takes no `workflow` argument in 3.1.0 even though `help set_current_workflow` suggests it.
- **The evaluation script's `console.log` goes to `project/workflows/server.log`**, not
  vspipeline's stdout; the driver's own `console.log` does reach stdout. Copy/cat the log.
- **`scriptName` resolution:** a value ending in `.js` is used as a path; otherwise
  `<name>/script_cancer.js` (or `script_acmg.js` for `acmg.runCustomScript`) under ReportTemplates.
- **`addCnv` may throw after succeeding** (its resolver looks up the new biomarker in a state
  snapshot taken before the add). Judge success by diffing `getEvaluationBiomarkers` before and
  after, not by the exception — otherwise a retry adds a duplicate.
- **`addCnv("<transcript> <exon> DEL")` ignores the exon**: `NM_000245.4 14 DEL` is accepted
  but becomes a whole-gene *MET Deletion*. Use genomic coordinates for exon-level CNVs (the
  shipped TSO500 splice script uses the transcript form, so it is affected too).

## Recipe: exon skipping events (e.g. MET exon 14)

VSClinical has a native `EXON_SKIPPING` annotation scope ("`<Gene> Exon <N> Skipping`"), and two
import routes reach it. Both verified on 3.1.0 EA5 / GRCh38, each yielding
**MET Exon 14 Skipping [EXON_SKIPPING]** as the biomarker's selected mutation:

| Route | Call | Biomarker description |
|---|---|---|
| Exon-level deletion of exactly the skipped exon(s) | `addCnv({ cnv: '7:116771849-116771989 DEL' })` | *Inframe Deletion* |
| The causal splice-site variant | `addVariant({ variant: 'NM_000245.4:c.3028+1G>T' })` | *Disrupt Acceptor Splice Site* |

The CNV route is the one for RNA-level skip calls (Archer "Exon(s) Skipped", TSO500 splice
variants): VSClinical offers *Exon Skipping* (ahead of *Exon N Deletion*) only when the deletion is
in frame; an out-of-frame exon loss becomes a *Truncation*. Compute the exon span from `preferredTranscriptForGene` (`exonStarts[i] + 1`
to `exonStops[j]`; on the minus strand exon N is index `exonCount - N`). The splice route only
offers *Exon Skipping* first when the splice predictors agree the variant disrupts splicing.
The example script `Import Exon Skipping Events` implements both routes (`MODE` constant) and
logs `OK` / `PARTIAL` (skipping offered but not selected) per event.
