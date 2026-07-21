# ghclient — Python SDK (agent field notes)

`ghclient` is the Python SDK for this workspace's API — files, catalogs, tasks, workflows — the
same surface as `gautil client` but as native objects. Pre-installed in the server image; any
task script can `from ghclient import GHClient` directly.

**Authoritative, version-matched reference on this server:**
`/opt/frontend/docs/tools/ghclient.md` — read it for the full method tables (`client.files`,
`client.catalogs`, `client.tasks`, `client.workflows`) and dataclass shapes. This file only
records the things that surprise agents.

```python
from ghclient import GHClient
client = GHClient()   # reads GH_WORKSPACE_URL + credentials from env; no args needed in a task
```

## Field notes
- **Auth precedence mirrors `gautil client`:** constructor kwargs > `GH_WORKSPACE_URL` >
  `GH_SERVER_URL`+`GH_WORKSPACE_ID`; and **`GH_SESSION_KEY` wins over `GH_API_KEY`** when both
  are set. In this agent runtime `GH_SESSION_KEY` is set, so `GHClient()` acts **as the current
  user**. In a task container `GH_WORKSPACE_URL` + `GH_API_KEY` are pre-set.
- **Catalogs are addressed by their `id`** (the human slug chosen at creation), never the UUID.
  The id equals the catalog filename minus `.catalog` and is returned by
  `client.catalogs.list()`.
- **Paths are workspace-relative** `"<location>/<path>"` — the first segment is the file
  location (`Documents`, `Catalogs`, `Automation`, ...). Same convention as `gautil client`.
- `client.tasks.wait(run_id)` **blocks** and returns a dict whose `status` is `"complete"` or
  `"failed"` (not `"success"`). Check it.
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
client.files.upload("Documents/reports/ard.md", "/scratch/ARD.md")
entries = client.files.list("Documents/reports")
client.files.download("Documents/reports/ard.md", "/scratch/")

# Catalogs
client.catalogs.upsert("CurationHistory", {"track": "brca", "qc_status": "staged"})
rows = client.catalogs.query("CurationHistory",
    filter_tree={"operator": "eq", "field": "track", "value": "brca"}, limit=10)

# Tasks / workflows from inside another task
run_id = client.tasks.run("Automation/Workflows/.../qc.task.yaml")
result = client.tasks.wait(run_id)          # {"status": "complete" | "failed", ...}
for line in client.tasks.log(run_id, follow=True):
    print(line)
```

> When to use which: reach for **`gautil client`** from shell/YAML steps and for the
> run→poll→log loop; reach for **`ghclient`** when you're already in Python and want typed
> objects (catalog upserts, file ops, orchestration). They authenticate identically.
