# VSClinical

Agent notes for scripting VSClinical (the ACMG and AMP evaluation workflows inside VarSeq).

| To… | Open |
|---|---|
| Write an evaluation script (`script_cancer.js` / `script_acmg.js`), find its API, or run one headlessly with `vspipeline` | [`evaluation-scripts.md`](./evaluation-scripts.md) |
| Copy a verified VSW task that runs an evaluation script end to end | [`examples/headless-evaluation-script/`](./examples/headless-evaluation-script/) |

The example folder holds `run_evaluation_script.task.yaml` (project → AMP evaluation → script →
biomarker dump), a one-sample VCF, and `Import Exon Skipping Events/`, a script that imports
exon skipping events such as MET exon 14 skipping from a TSV.
