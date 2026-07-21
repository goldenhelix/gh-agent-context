# server-index — what's installed on this server

Searchable Markdown indexes of the task/workflow/plugin/application definitions that ship on
**this** VS Warehouse server, so an agent can grep one file instead of walking the filesystem.
These are the best worked examples to copy from and adapt.

| File | Indexes | Source on server |
|---|---|---|
| [`built-in-tasks.md`](./built-in-tasks.md) | Built-in `System/` tasks (available in every workspace) | `/opt/backend/tasks/` |
| [`server-templates.md`](./server-templates.md) | Template tasks, workflows, plugins, applications | `/opt/server_templates/workspaces/*/Automation/` |
| [`generate-index.py`](./generate-index.py) | — regenerates both indexes | — |

## Usage
- **Find an example:** grep these files for a keyword (`grep -i catalog server-index/*.md`),
  then open the referenced source path with `Read` to see the full definition.
- **Run a built-in task:** they live under the `System/` path, e.g.
  `gautil client task-run System/create_catalog -p ...`.
- **Adapt a template:** copy the referenced file into your workspace's `Automation/Workflows/`
  tree (that's where the runner discovers tasks — see
  [`../vswarehouse/reference/agent-loop.md`](../vswarehouse/reference/agent-loop.md)), then edit.

## Regenerating
Run after a server upgrade (the indexes are committed so off-server clones have something to
search, but the server files are the source of truth):
```bash
python3 server-index/generate-index.py
```
The script reads the paths above and rewrites `built-in-tasks.md` and `server-templates.md`.
