# VS Warehouse REST API specs

Machine-readable OpenAPI specs for the VS Warehouse REST API (the prose overview is the server
doc at `/opt/frontend/docs/api-docs.md`; these are the contracts it defers to). **Prefer the live
specs on the box you're on** — every agent already has a session, and `GET /auth/api/me/openApiUrls`
lists the current set:

- the **Auth / Admin Server API** at `/auth/api/openapi.json` (server config, licensing,
  user/session management, runners & agents, server events, workspaces). Server-wide.
- the per-workspace **Workflow (mcp) API** at `/w/<workspace>/mcp/openapi.json` (run/monitor
  tasks & workflows). Its `info.title` is also `"Golden Helix Admin Server API"` — same title as
  the Auth API, so key off the URL/filename, not the title, when telling specs apart.
- the per-workspace **Catalogs / Files / Lookup** APIs at `/w/<workspace>/api/catalogs.yaml`,
  `/w/<workspace>/api/files.yaml`, `/w/<workspace>/api/lookup.yaml`.

Substitute your own workspace id for `<workspace>` in every per-workspace path.

One endpoint the Lookup API depends on is in none of these specs:
`POST /w/<workspace>/api/annotations/refresh` (body `{}`, returns `"REFRESH_COMPLETE"`) rescans
the annotation folders so a newly uploaded source resolves. See
[`../reference/annotation-lookup.md`](../reference/annotation-lookup.md).

This folder also carries a static, possibly-stale snapshot of those same specs, downloaded by
[`refresh-api-specs.py`](./refresh-api-specs.py) (this repo pins no version — treat the committed
copies only as an offline fallback, never as the contract of record).

## Refreshing
`refresh-api-specs.py` authenticates exactly like the shipped server tasks: `GET
/auth/api/authenticationMethod` → `.sessionCookieName` (here `GH_SessKey`), then sends `Cookie:
GH_SessKey=$GH_SESSION_KEY`, lists specs at `/auth/api/me/openApiUrls`, and downloads each. It
writes next to itself in this checkout, so re-running it only refreshes the committed copies when
this checkout's location is mounted read-write, which requires an admin launch — a normal agent
launch has this location read-only and the write will fail. If you just need the current contract,
skip the script and hit `/auth/api/me/openApiUrls` (or the fixed paths above) directly with your
session cookie instead of trying to write into this checkout.
