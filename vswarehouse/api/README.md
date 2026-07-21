# VS Warehouse REST API specs

Machine-readable OpenAPI specs for the VS Warehouse REST API (the prose overview is the server
doc at `/opt/frontend/docs/api-docs.md`; these are the contracts it defers to). These static
copies are re-downloaded from whatever server [`refresh-api-specs.py`](./refresh-api-specs.py) is
run against — **prefer the live specs on the box you're on**, and re-run the script after a
server upgrade to refresh them (this repo pins no version).

- **`openapi.json`** — the **Auth / Admin Server API** (server config, licensing, user/session
  management, runners & agents, server events, workspaces). Server-wide.
- **`workflow-api.json`** — the per-workspace **Workflow (mcp) API** (run/monitor tasks & workflows).
- **`catalogs-api.yaml`**, **`files-api.yaml`**, **`lookup-api.yaml`** — the per-workspace
  **Catalogs / Files / Lookup** APIs.

The per-workspace APIs are served under a workspace path prefix — `/w/<workspace>/mcp/...`,
`/w/<workspace>/api/...`. These copies were captured from a Golden Helix product workspace as the
representative shape; substitute your own workspace id in the path.

## Refreshing
Run [`refresh-api-specs.py`](./refresh-api-specs.py) on the server (the `GH_*` env is already
set in the agent runtime):
```bash
python3 vswarehouse/api/refresh-api-specs.py          # this workspace's + the Auth specs
python3 vswarehouse/api/refresh-api-specs.py --all    # every workspace's specs too
```
It authenticates exactly like the shipped server tasks: `GET /auth/api/authenticationMethod` →
`.sessionCookieName` (here `GH_SessKey`), then sends `Cookie: GH_SessKey=$GH_SESSION_KEY`, lists
specs at `/auth/api/me/openApiUrls`, and downloads each. An agent that just needs the current
contract can hit those endpoints directly instead of relying on these committed copies.
