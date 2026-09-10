# Built-in (system) tasks

System tasks shipped with the server, available in **every** workspace under the
`System/` task path (run them with `gautil client task-run System/<name>`).
Source on this server: `/opt/backend/tasks/`. Regenerate with
`server-index/generate-index.py`.

| Task path | Name | Parameters | Description |
|---|---|---|---|
| `System/add_catalog_fields` | Add Catalog Fields from Schema | schema_file:file, catalog_id:string | Add fields defined in a schema YAML file to an existing catalog, skipping fields that already exist |
| `System/application_checkout` | Application Repository Checkout | application_url:string, image_url:string, image_var:string?, image_name:string?, base_path:directory | Checkout an application and its associated Docker image |
| `System/create_catalog` | Create Workspace Catalogs | sample:boolean, germline_sample_fields:enum[]?, somatic_sample_fields:enum[]?, pgx_sample_fields:enum[]?, report_fields:enum[]?, gene_list_catalog:boolean, gene_preferences_catalog:boolean, update_legacy_gene_catalogs:boolean, vsclinical_acmg_catalogs:boolean, vsclinical_amp_catalogs:boolean, sample_catalog_id:string, sample_catalog_name:string, sample_catalog_description:string | Create default workspace catalogs |
| `System/download_annotation_source` | Download Annotation Source | series:string, coordSysId:string | Download a single annotation source series into the workspace annotations |
| `System/download_annotations` | Download or Update Workspace Annotations | reference:boolean, other_reference:boolean, genes_refseq:boolean, genes_ensembl:boolean, ontologies_germline:boolean, clinical_germline:boolean, clinical_germline_recommended:boolean, ontologies_somatic:boolean, clinical_somatic:boolean, clinical_somatic_recommended:boolean, cadd:boolean, gnomad_joint:boolean, msa:boolean, panel_app:boolean, clingen_expert:boolean | Download and update the annotations used by VarSeq and VSPipeline to perform different types of analysis |
| `System/plugin_checkout` | Plugin Repository Checkout | plugin_url:string, image_url:string?, image_var:string?, image_name:string?, base_path:directory | Checkout a plugin and its associated Docker image |
| `System/storage_diagnostics` | Storage Diagnostics | target_dir:directory, report_dir:directory?, write_verify:boolean, duration_seconds:integer, read_saturation:boolean, levels:string, local_baseline:boolean, two_view:boolean, rounds:integer, allow_same_kernel:boolean, max_total_mb:integer | Run the VarSeq storage diagnostics against a workspace folder - write visibility, read saturation and two-view consistency |
| `System/system_report` | System Report | — | Generates a system report including hostname, uptime, kernel version, CPU info, memory info, disk usage, and network interfaces. |
| `System/workflow_check_update` | Check Workflow Repository Updates | base_path:directory | Check all checked out workflow repositories for available updates |
| `System/workflow_checkout` | Workflow Repository Checkout | github_url:string, folder_name:string?, base_path:directory, checkout_ref:string? | Checkout a workflow repository to the Automation folder from GitHub |

_10 built-in tasks indexed._
