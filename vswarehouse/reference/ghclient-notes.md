# ghclient — Python SDK (agent field notes)

`ghclient` is the Python SDK for this workspace's API — files, catalogs, tasks, workflows, ai — the
same surface as `gautil client` but as native objects. Pre-installed in the server image; any
task script can `from ghclient import GHClient` directly.

**Authoritative, version-matched reference on this server:**
`/opt/frontend/docs/tools/ghclient.md` — read it for the full method tables (`client.files`,
`client.catalogs`, `client.tasks`, `client.workflows`, `client.ai`) and dataclass shapes. This
file only records the things that surprise agents.

```python
from ghclient import GHClient
client = GHClient()   # composes GH_SERVER_URL + GH_WORKSPACE_ID and reads GH_SESSION_KEY from env
```

## Field notes
- **URL resolution:** `workspace_url=` > `GH_WORKSPACE_URL` > `server_url=`/`GH_SERVER_URL` +
  `workspace_id=`/`GH_WORKSPACE_ID` (the `server_url=`/`workspace_id=` kwargs are ignored whenever
  `GH_WORKSPACE_URL` is set). **`GH_SESSION_KEY` wins over `GH_API_KEY` in `ghclient`**, the
  opposite of `gautil client`, which prefers `GH_API_KEY` and only falls back to the session
  cookie: if both are set in one shell the CLI and the SDK can act as different identities. In
  this agent runtime `GH_SESSION_KEY` is set, so `GHClient()` acts **as the current user**. In a
  task container the server sets `GH_SERVER_URL` + `GH_WORKSPACE_ID` (not `GH_WORKSPACE_URL`),
  which `GHClient()` composes into the workspace URL. Nothing sets `GH_API_KEY`: a task only gets
  credentials if its YAML declares `auto_generate_session_for_account: '{user}'` (or
  `{workspaceBot}` / `{workspaceAdminBot}`), which injects `GH_SESSION_KEY`. Without that line
  `GHClient()` constructs fine and then every call fails unauthenticated.
- `client.ai` (models / is_enabled / prompts / transform_text) is the workspace-AI sub-client, the
  SDK equivalent of `gautil client ai-transform`; it is missing from the bundled doc's sub-client
  tables.
- **Catalogs are addressed by their `id`** (the human slug chosen at creation), never the UUID.
  The id equals the catalog filename minus `.catalog` and is returned by
  `client.catalogs.list()`.
- **Paths are workspace-relative** `"<location>/<path>"` — the first segment is the file
  location (`Documents`, `Catalogs`, `Automation`, ...). Same convention as `gautil client`.
- `client.tasks.wait(run_id)` **blocks** and returns the status dict; success is `"completed"`,
  failure `"failed"` (never `"complete"` or `"success"`). It also only breaks on
  `complete/completed/failed/cancelled`, but the server writes `canceled` (one l), so a
  canceled/deleted/skipped run makes `wait()` and `log(follow=True)` poll forever: always pass
  `timeout=` to `wait()`, and treat `status(run_id)['status'] in {'completed', 'failed',
  'canceled', 'deleted', 'skipped'}` as terminal if you poll yourself.
- Errors raise `GHClientError` with `.status_code` and `.body`:
  ```python
  from ghclient import GHClient, GHClientError
  try:
      client.catalogs.info("nope")
  except GHClientError as e:
      print(e.status_code, e.body)
  ```

## Common recipes
```python
# Files
client.files.upload("Documents/reports/ard.md", "/scratch/ARD.md", overwrite=True)
resp = client.files.list("Documents/reports")
for e in resp.entries:
    ...
client.files.download("Documents/reports/ard.md", "/scratch/")

# Catalogs
rec = client.catalogs.upsert("CurationHistory", {"track": "brca", "qc_status": "staged"})
client.catalogs.record_publish("CurationHistory", rec.id, rec.history_id)
# or client.catalogs.write_records("CurationHistory", objects=[...]) to write published rows in bulk

from ghclient.types import ExpressionNode, OperatorType
resp = client.catalogs.query("CurationHistory",
    filter_tree=ExpressionNode(op=OperatorType.EQUALS, field="track", value="brca"), limit=10)
for row in resp.data.values:
    ...

# Tasks / workflows from inside another task
run_id = client.tasks.run("qc-folder/qc.task.yaml", parameters=[{"name": "n", "value": "1"}])
result = client.tasks.wait(run_id, timeout=300)   # {"status": "completed" | "failed", ...}
for line in client.tasks.log(run_id, follow=True):
    print(line)
for line in client.tasks.log(run_id, stream="stderr", follow=True):
    print(line)
```

- Uploads are not idempotent by default: without `overwrite=True` an existing destination raises
  `GHClientError` ("file already exists"); parent folders are created for you.
- `files.list()` and `catalogs.query()` return response dataclasses, not bare lists: entries live
  at `resp.entries` and `resp.data.values` respectively. `resp.data.values` is column-ordered per
  `resp.data.fields`; `query()` defaults to `limit=100` — page with `offset` while `resp.has_more`,
  or use `query_all()`.
- `upsert()` writes a **draft**: the row won't appear in a default query until published with
  `record_publish(catalog_id, rec.id, rec.history_id)`, or use `write_records(...)` to write
  published rows directly (needs the `catalog:publish` permission). Unlike the `gautil client` CLI,
  the SDK does no server-side merge, so fields omitted from `data` are not carried over from an
  existing published record: write the complete field set, and include the catalog's primary-key
  field(s) with `record_id` omitted for idempotency.
- Catalog filters are `ExpressionNode` objects, not dicts; the key is `op` with `OperatorType`
  values (`Equals`, `StartsWith`, ...), and compound filters nest under `children`.
- Task paths are relative to `Automation/Workflows/` (built-ins are `System/<name>`), extension
  optional; a leading `Automation/Workflows/` prefix 404s.
- `log()` is per-stream and defaults to `stream="stdout"`: read `stream="stderr"` separately —
  there is no interleaved mode as in `gautil client task-log`.

> When to use which: reach for **`gautil client`** from shell/YAML steps and for the
> run→poll→log loop; reach for **`ghclient`** when you're already in Python and want typed
> objects (catalog upserts, file ops, orchestration). They accept the same credentials, but see
> the auth-precedence note above: with both `GH_SESSION_KEY` and `GH_API_KEY` set, the two tools
> can act as different identities.
